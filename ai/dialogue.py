"""
Многоходовой диалог переговоров.

Публичные функции:
    start_negotiation(mode, theme, custom_situation, difficulty, character_level)
        -> (StartResult | RejectionResult, Session | None)
        Session is None тогда и только тогда, когда вернулся RejectionResult.
    advance_turn(session, player_message) -> (TurnResult, Session)

Session — обычный dataclass, который вызывающая сторона хранит между HTTP-запросами
(в памяти, в БД, или просто прогоняет через фронтенд) и сериализует через
Session.to_dict()/Session.from_dict().
"""
import os
import random
from dataclasses import replace

from . import llm, prompts, rag
from .contracts import (
    ContractError, DialogueTurn, Feedback, RejectionResult, Session, StartResult, TurnResult,
    OPTIONS_COUNT, REJECTION_REASONS, SAFETY_MAX_TURNS,
    _require_text, _optional_text, _to_bool, _check_score, _parse_options, validate_request,
)

# MAX_ATTEMPTS (повтор при схемно-неверном, но синтаксически валидном JSON) умножается
# на retries внутри llm.chat_json (повтор при сетевой ошибке/битом JSON) — оба снижены,
# чтобы держать задержку в худшем случае под контролем: 2 x 2 = 4 запроса максимум,
# а не 9, как было раньше. В обычном случае происходит ровно один запрос на ход.
MAX_ATTEMPTS = 2

# max_tokens — это ПОТОЛОК длины ответа, а не целевая длина: если модель естественно
# укладывается в 200 токенов, лимит в 700 не делает её медленнее. Держим его не впритык,
# а с запасом — у части моделей Qwen3 по умолчанию включено скрытое "размышление" перед
# ответом (см. ai/llm.py), и слишком тесный лимит рискует обрезать сам JSON-ответ раньше,
# чем размышление закончится. START больше, потому что там же описание сцены и роль
# оппонента; TURN общий и для продолжения, и для завершающего хода (там же feedback).
START_MAX_TOKENS = int(os.environ.get("QWEN_START_MAX_TOKENS", 700))
TURN_MAX_TOKENS = int(os.environ.get("QWEN_TURN_MAX_TOKENS", 600))

# Не тащим в промпт больше 3 карточек методик сразу — это и держит подсказку короче,
# и не даёт модели распыляться на слишком много несвязанных техник за один ход.
MAX_CARDS_PER_TURN = 3


def _parse_start_response(raw: dict, mode: str, difficulty: int, allowed_ids: set[str]):
    """-> StartResult | RejectionResult. Ветка отказа возможна только при mode='custom' —
    в mode='theme' тема всегда из нашего же списка, проверять валидность нечего."""
    if mode == "custom":
        is_negotiation = _to_bool(raw.get("is_negotiation", True), "is_negotiation")
        if not is_negotiation:
            reason = raw.get("rejection_reason")
            if reason not in REJECTION_REASONS:
                raise ContractError(f"rejection_reason должен быть одним из {REJECTION_REASONS}, получено: {reason!r}")
            return RejectionResult(reason=reason)

    principles = [i for i in raw.get("principles_used", []) if i in allowed_ids] or sorted(allowed_ids)
    return StartResult(
        scenario_text=_require_text(raw.get("scenario_text"), "scenario_text"),
        counterpart_opening=_require_text(raw.get("counterpart_opening"), "counterpart_opening"),
        counterpart_role=_require_text(raw.get("counterpart_role"), "counterpart_role"),
        counterpart_tone=_require_text(raw.get("counterpart_tone"), "counterpart_tone"),
        counterpart_goal=_require_text(raw.get("counterpart_goal"), "counterpart_goal"),
        difficulty=difficulty,
        principles_used=principles,
        options=_parse_options(raw.get("options"), difficulty),
    )


def start_negotiation(mode: str, difficulty: int, character_level: int,
                       theme: str | None = None, custom_situation: str | None = None):
    """
    mode="theme"  -> нужен theme (одна из ai.THEMES), custom_situation игнорируется.
    mode="custom" -> нужен custom_situation (текст пользователя), theme игнорируется.

    -> (StartResult, Session) в обычном случае.
    -> (RejectionResult, None) если mode="custom" и модель отказалась строить сценарий
       (текст не про переговоры / слишком расплывчатый / небезопасный).
    Бросает ContractError (неверные входные данные) или AIError (Qwen не ответил).
    """
    validate_request(mode, theme, custom_situation, difficulty, character_level)

    cards = rag.cards_for_scenario(character_level)
    allowed_ids = {c["id"] for c in cards}
    materials = rag.format_cards(cards)
    if mode == "theme":
        system, user_prompt = prompts.START_SYSTEM, prompts.start_user_theme(theme, difficulty, character_level, materials)
    else:
        system, user_prompt = prompts.CUSTOM_START_SYSTEM, prompts.start_user_custom(custom_situation, difficulty, character_level, materials)

    start = None
    last_error = None
    for _ in range(MAX_ATTEMPTS):
        raw = llm.chat_json(system, user_prompt, temperature=0.8, max_tokens=START_MAX_TOKENS)
        try:
            start = _parse_start_response(raw, mode, difficulty, allowed_ids)
            break
        except ContractError as e:
            last_error = e
    if start is None:
        raise llm.AIError(f"Не удалось сгенерировать корректный сценарий: {last_error}")

    if isinstance(start, RejectionResult):
        return start, None

    session = Session(
        theme=theme if mode == "theme" else None,
        difficulty=difficulty,
        character_level=character_level,
        counterpart_role=start.counterpart_role,
        counterpart_tone=start.counterpart_tone,
        counterpart_goal=start.counterpart_goal,
        scenario_text=start.scenario_text,
        principles_used=start.principles_used,
        turns_done=0,
        finished=False,
        transcript=[DialogueTurn(speaker="counterpart", text=start.counterpart_opening)],
    )
    return start, session


def _degrade_feedback_to_text(raw_feedback) -> str:
    """Деградация: структуру собрать не вышло даже после повтора, но игру всё равно
    нужно довести до конца — заворачиваем что есть в одну строку вместо объекта."""
    if isinstance(raw_feedback, str) and raw_feedback.strip():
        return raw_feedback.strip()
    if isinstance(raw_feedback, dict):
        parts = [v.strip() for v in raw_feedback.values() if isinstance(v, str) and v.strip()]
        if parts:
            return " ".join(parts)
    return "Не удалось получить развёрнутую обратную связь для этого раунда."


def _parse_feedback(raw_feedback, lenient: bool):
    """-> Feedback (структурный разбор) | str (деградация). Деградация допустима
    ТОЛЬКО когда lenient=True — то есть на последней попытке (см. advance_turn):
    сначала пробуем строго, и лишь если строгая схема дважды не собралась, отдаём
    просто текст вместо ошибки, которая иначе остановила бы всю игру."""
    if isinstance(raw_feedback, dict):
        try:
            return Feedback(
                tip=_require_text(raw_feedback.get("tip"), "feedback.tip"),
                broke_quote=_optional_text(raw_feedback.get("broke_quote")),
                broke_reason=_optional_text(raw_feedback.get("broke_reason")),
                what_worked=_optional_text(raw_feedback.get("what_worked")),
                alternative_phrasing=_optional_text(raw_feedback.get("alternative_phrasing")),
            )
        except ContractError:
            if not lenient:
                raise
            return _degrade_feedback_to_text(raw_feedback)
    if not lenient:
        raise ContractError(f"feedback должен быть объектом по строгой схеме, получено: {raw_feedback!r}")
    return _degrade_feedback_to_text(raw_feedback)


def _parse_turn_response(raw: dict, session: Session, force_end: bool, lenient_feedback: bool) -> TurnResult:
    ends = _to_bool(raw.get("ends"), "ends")
    if force_end and not ends:
        raise ContractError("При форсированном завершении (технический потолок) ends должен быть true")
    counterpart_reply = _require_text(raw.get("counterpart_reply"), "counterpart_reply")

    if ends:
        outcome = raw.get("outcome")
        score = _check_score(outcome, raw.get("score"))
        feedback = _parse_feedback(raw.get("feedback"), lenient_feedback)
        if isinstance(feedback, Feedback):
            return TurnResult(ends=True, counterpart_reply=counterpart_reply,
                               outcome=outcome, score=score, feedback=feedback)
        return TurnResult(ends=True, counterpart_reply=counterpart_reply,
                           outcome=outcome, score=score, feedback_degraded_text=feedback)

    options = _parse_options(raw.get("options"), session.difficulty)
    if session.difficulty in OPTIONS_COUNT and options is None:
        raise ContractError("Ожидались options для продолжения диалога на этой сложности")
    return TurnResult(ends=False, counterpart_reply=counterpart_reply, options=options)


def advance_turn(session: Session, player_message: str) -> tuple[TurnResult, Session]:
    if session.finished:
        raise ContractError("Переговоры уже завершены, новый ход невозможен")
    player_message = _require_text(player_message, "player_message")

    # Игрового лимита ходов нет — это только аварийный технический потолок (см. contracts.py),
    # который почти никогда не должен срабатывать при нормальной игре.
    force_end = session.turns_done + 1 >= SAFETY_MAX_TURNS

    cards = rag.get_by_ids(session.principles_used)
    for c in rag.search(player_message):
        if c not in cards:
            cards.append(c)
    cards = cards[:MAX_CARDS_PER_TURN]
    user_prompt = prompts.turn_user(session, player_message, rag.format_cards(cards), force_end)

    result = None
    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        raw = llm.chat_json(prompts.TURN_SYSTEM, user_prompt, temperature=0.4, max_tokens=TURN_MAX_TOKENS)
        # lenient_feedback=True только на последней попытке: строгую JSON-схему разбора
        # (Feedback) даём модели два шанса собрать, а если и тогда не вышло — деградируем
        # feedback до простого текста вместо того, чтобы ронять весь ход ошибкой.
        is_last_attempt = attempt == MAX_ATTEMPTS - 1
        try:
            result = _parse_turn_response(raw, session, force_end, lenient_feedback=is_last_attempt)
            break
        except ContractError as e:
            last_error = e
    if result is None:
        raise llm.AIError(f"Не удалось получить корректный ответ на ход диалога: {last_error}")

    # Сессия обновляется только после успешного разбора ответа модели.
    new_transcript = session.transcript + [
        DialogueTurn(speaker="player", text=player_message),
        DialogueTurn(speaker="counterpart", text=result.counterpart_reply),
    ]
    session = replace(session, turns_done=session.turns_done + 1,
                       transcript=new_transcript, finished=result.ends)
    return result, session
