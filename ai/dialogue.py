"""
Многоходовой диалог переговоров.

Публичные функции:
    start_negotiation(theme, difficulty, character_level) -> (StartResult, Session)
    advance_turn(session, player_message)                -> (TurnResult, Session)

Session — обычный dataclass, который бэкенд хранит между HTTP-запросами
(в памяти или в БД) и сериализует через Session.to_dict()/Session.from_dict().
"""
import os
import random
from dataclasses import replace

from . import llm, prompts, rag
from .contracts import (
    ContractError, DialogueTurn, Session, StartResult, TurnResult,
    TURNS_RANGE, OPTIONS_COUNT,
    _require_text, _to_bool, _check_score, _parse_options, validate_request,
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
# оппонента; TURN общий и для продолжения, и для завершающего хода (там же feedback_text).
START_MAX_TOKENS = int(os.environ.get("QWEN_START_MAX_TOKENS", 700))
TURN_MAX_TOKENS = int(os.environ.get("QWEN_TURN_MAX_TOKENS", 600))

# Не тащим в промпт больше 3 карточек методик сразу — это и держит подсказку короче,
# и не даёт модели распыляться на слишком много несвязанных техник за один ход.
MAX_CARDS_PER_TURN = 3


def _parse_start_response(raw: dict, difficulty: int, allowed_ids: set[str], max_turns: int) -> StartResult:
    principles = [i for i in raw.get("principles_used", []) if i in allowed_ids] or sorted(allowed_ids)
    return StartResult(
        scenario_text=_require_text(raw.get("scenario_text"), "scenario_text"),
        counterpart_opening=_require_text(raw.get("counterpart_opening"), "counterpart_opening"),
        counterpart_role=_require_text(raw.get("counterpart_role"), "counterpart_role"),
        counterpart_tone=_require_text(raw.get("counterpart_tone"), "counterpart_tone"),
        counterpart_goal=_require_text(raw.get("counterpart_goal"), "counterpart_goal"),
        difficulty=difficulty,
        max_turns=max_turns,
        principles_used=principles,
        options=_parse_options(raw.get("options"), difficulty),
    )


def start_negotiation(theme: str, difficulty: int, character_level: int) -> tuple[StartResult, Session]:
    validate_request(theme, difficulty, character_level)
    lo, hi = TURNS_RANGE[difficulty]
    max_turns = random.randint(lo, hi)

    cards = rag.cards_for_scenario(character_level)
    allowed_ids = {c["id"] for c in cards}
    user_prompt = prompts.start_user(theme, difficulty, character_level, rag.format_cards(cards), max_turns)

    start = None
    last_error = None
    for _ in range(MAX_ATTEMPTS):
        raw = llm.chat_json(prompts.START_SYSTEM, user_prompt, temperature=0.8, max_tokens=START_MAX_TOKENS)
        try:
            start = _parse_start_response(raw, difficulty, allowed_ids, max_turns)
            break
        except ContractError as e:
            last_error = e
    if start is None:
        raise llm.AIError(f"Не удалось сгенерировать корректный сценарий: {last_error}")

    session = Session(
        theme=theme,
        difficulty=difficulty,
        character_level=character_level,
        counterpart_role=start.counterpart_role,
        counterpart_tone=start.counterpart_tone,
        counterpart_goal=start.counterpart_goal,
        scenario_text=start.scenario_text,
        principles_used=start.principles_used,
        max_turns=max_turns,
        turns_done=0,
        finished=False,
        transcript=[DialogueTurn(speaker="counterpart", text=start.counterpart_opening)],
    )
    return start, session


def _parse_turn_response(raw: dict, session: Session, is_final_turn: bool) -> TurnResult:
    ends = _to_bool(raw.get("ends"), "ends")
    if is_final_turn and not ends:
        raise ContractError("На последнем доступном ходу ends должен быть true")
    counterpart_reply = _require_text(raw.get("counterpart_reply"), "counterpart_reply")

    if ends:
        outcome = raw.get("outcome")
        score = _check_score(outcome, raw.get("score"))
        feedback = _require_text(raw.get("feedback_text"), "feedback_text")
        return TurnResult(ends=True, counterpart_reply=counterpart_reply,
                           outcome=outcome, score=score, feedback_text=feedback)

    options = _parse_options(raw.get("options"), session.difficulty)
    if session.difficulty in OPTIONS_COUNT and options is None:
        raise ContractError("Ожидались options для продолжения диалога на этой сложности")
    return TurnResult(ends=False, counterpart_reply=counterpart_reply, options=options)


def advance_turn(session: Session, player_message: str) -> tuple[TurnResult, Session]:
    if session.finished:
        raise ContractError("Переговоры уже завершены, новый ход невозможен")
    player_message = _require_text(player_message, "player_message")
    is_final_turn = session.turns_remaining() <= 1

    cards = rag.get_by_ids(session.principles_used)
    for c in rag.search(player_message):
        if c not in cards:
            cards.append(c)
    cards = cards[:MAX_CARDS_PER_TURN]
    user_prompt = prompts.turn_user(session, player_message, rag.format_cards(cards), is_final_turn)

    result = None
    last_error = None
    for _ in range(MAX_ATTEMPTS):
        raw = llm.chat_json(prompts.TURN_SYSTEM, user_prompt, temperature=0.4, max_tokens=TURN_MAX_TOKENS)
        try:
            result = _parse_turn_response(raw, session, is_final_turn)
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
