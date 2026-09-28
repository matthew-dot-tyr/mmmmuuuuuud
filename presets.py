"""
presets.py — единственная точка входа для бэкенда в AI-модуль переговорщика.
main.py импортирует отсюда, движок (ai/) не трогаем — это только переходник
имён/формата под то, что нужно бэкенду.

    from presets import start_negotiation, advance_turn, THEMES, PRESETS

XP не считаем здесь: единственный источник правды — progress.py::calculate_xp_gain
(см. README, раздел "Начисление XP").

Ничего не хранит между запросами. Session, который возвращает start_negotiation
и advance_turn, — обычный dict: его нужно просто сохранить (в бэкенде или,
если решили гонять историю через фронтенд — там) и прислать обратно на
следующем ходу без изменений. Внутри он всегда сериализуемый в JSON.

Лимита ходов в контракте нет: диалог продолжается, пока модель не решит его
закончить. Есть только скрытый технический потолок на случай зацикливания —
он не выведен ни в один публичный ответ этого модуля.

Ошибки:
  ContractError — неверные входные данные (плохие theme/custom_situation/difficulty/
                  session и т.п.) -> HTTP 400.
  AIError       — Qwen не ответил или вернул непригодный JSON после повторных попыток
                  -> HTTP 503.
Обе кидает и start_negotiation, и advance_turn.
"""
from ai import (
    start_negotiation as _start_negotiation,
    advance_turn as _advance_turn,
    Session,
    RejectionResult,
    ContractError,
    AIError,
    THEMES,
    MODES,
)

__all__ = [
    "start_negotiation", "advance_turn",
    "THEMES", "MODES", "PRESETS", "ContractError", "AIError",
]

# Готовые пары тема+сложность — чтобы можно было поднять сервер и прогнать
# путь генератор -> судья целиком одной строкой, не выдумывая входные данные.
PRESETS = [
    {"mode": "theme", "theme": THEMES[0], "difficulty": 1, "character_level": 1},
    {"mode": "theme", "theme": THEMES[1], "difficulty": 2, "character_level": 3},
    {"mode": "theme", "theme": THEMES[2], "difficulty": 3, "character_level": 5},
]


def start_negotiation(mode: str, difficulty: int, character_level: int,
                       theme: str | None = None, custom_situation: str | None = None) -> dict:
    """
    Начинает переговоры (Контракт "генератор"). Бросает ContractError/AIError.

    mode="theme"  -> theme обязателен (одна из THEMES), custom_situation не нужен.
    mode="custom" -> custom_situation обязателен (текст пользователя), theme не нужен.
    Правило «сложность не выше уровня персонажа» здесь не проверяется — это игровое
    правило, ему место на уровне бэкенда (у вас оно уже применяется до вызова этой
    функции), а не в AI-модуле.

    -> при успехе:
         {
           "session": {...},                       # прислать обратно как есть в advance_turn
           "scenario_text": "...",
           "counterpart_opening": "...",            # первая реплика оппонента
           "counterpart_role": "...",
           "counterpart_tone": "...",
           "counterpart_goal": "...",
           "options": [{"option_id": "a", "text": "..."}, ...],  # НЕТ ключа на сложности 3
         }
       при отказе (возможен только для mode="custom" — введённый текст не про
       переговоры, слишком расплывчатый или небезопасный; session не возвращается):
         {"rejected": True, "reason": "not_a_negotiation" | "too_vague" | "unsafe"}
    """
    start, session = _start_negotiation(mode, difficulty, character_level, theme, custom_situation)
    if isinstance(start, RejectionResult):
        return start.public()
    return {"session": session.to_dict(), **start.public()}


def advance_turn(session: dict, player_message: str) -> dict:
    """
    Один ход диалога (Контракт "судья", он же ведёт диалог дальше). Бросает
    ContractError/AIError.

    session — то, что вернул предыдущий start_negotiation/advance_turn под
    ключом "session". Прокидывайте его насквозь, ничего в нём трогать не надо.

    player_message — текст реплики игрока: на сложности 1-2 это ТЕКСТ выбранного
    варианта (не его option_id — найдите текст по id в options из предыдущего
    ответа перед вызовом), на сложности 3 — то, что игрок напечатал сам.

    -> при "continue": true (диалог продолжается):
         {"continue": true, "counterpart_reply": "...", "session": {...},
          "options": [...]}                       # options нет на сложности 3
       при "continue": false (переговоры завершены, session не возвращается —
       хранить больше нечего):
         {"continue": false, "counterpart_reply": "...",
          "outcome": "success" | "failure",
          "score": 1..10 | null,                  # null при failure
          "feedback": {                            # структурный разбор — ОБЫЧНО объект:
            "broke_quote": "..." | null,           #   точная цитата реплики игрока,
            "broke_reason": "..." | null,          #   где пошло не так, и почему;
            "what_worked": "..." | null,           #   null-поля значат "неприменимо"
            "alternative_phrasing": "..." | null,  #   (например, при чистом успехе)
            "tip": "..."                           #   единственное всегда заполненное поле
          }
          # ВАЖНО: если модель дважды не смогла собрать структуру, "feedback" —
          # обычная СТРОКА вместо объекта (деградация, чтобы не ронять весь ход
          # ошибкой). Проверяйте тип на своей стороне: isinstance(feedback, str).
    """
    result, new_session = _advance_turn(Session.from_dict(session), player_message)
    public = result.public()
    ends = public.pop("ends")
    if ends:
        return {"continue": False, **public}
    return {"continue": True, "session": new_session.to_dict(), **public}
