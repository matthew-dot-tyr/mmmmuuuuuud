"""
presets.py — единственная точка входа для бэкенда в AI-модуль переговорщика.
main.py импортирует отсюда, движок (ai/) не трогаем — это только переходник
имён/формата под то, что нужно бэкенду.

    from presets import start_negotiation, advance_turn, calculate_xp, THEMES, PRESETS

Ничего не хранит между запросами. Session, который возвращает start_negotiation
и advance_turn, — обычный dict: его нужно просто сохранить (в бэкенде или,
если решили гонять историю через фронтенд — там) и прислать обратно на
следующем ходу без изменений. Внутри он всегда сериализуемый в JSON.

Ошибки:
  ContractError — неверные входные данные (плохие theme/difficulty/session и т.п.) -> HTTP 400.
  AIError       — Qwen не ответил или вернул непригодный JSON после повторных попыток -> HTTP 503.
Обе кидает и start_negotiation, и advance_turn.
"""
from ai import (
    start_negotiation as _start_negotiation,
    advance_turn as _advance_turn,
    calculate_xp,
    Session,
    ContractError,
    AIError,
    THEMES,
)

__all__ = [
    "start_negotiation", "advance_turn", "calculate_xp",
    "THEMES", "PRESETS", "ContractError", "AIError",
]

# Готовые пары тема+сложность — чтобы можно было поднять сервер и прогнать
# путь генератор -> судья целиком одной строкой, не выдумывая входные данные.
PRESETS = [
    {"theme": THEMES[0], "difficulty": 1, "character_level": 1},
    {"theme": THEMES[1], "difficulty": 2, "character_level": 3},
    {"theme": THEMES[2], "difficulty": 3, "character_level": 5},
]


def start_negotiation(theme: str, difficulty: int, character_level: int) -> dict:
    """
    Начинает переговоры (Контракт "генератор"). Бросает ContractError/AIError.

    -> {
         "session": {...},                       # прислать обратно как есть в advance_turn
         "scenario_text": "...",
         "counterpart_opening": "...",            # первая реплика оппонента
         "counterpart_role": "...",
         "counterpart_tone": "...",
         "counterpart_goal": "...",
         "max_turns": 3,                          # потолок ходов игрока для этой сложности
         "options": [{"option_id": "a", "text": "..."}, ...],  # НЕТ ключа на сложности 3
       }
    """
    start, session = _start_negotiation(theme, difficulty, character_level)
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
          "feedback_text": "..."}
    """
    result, new_session = _advance_turn(Session.from_dict(session), player_message)
    public = result.public()
    ends = public.pop("ends")
    if ends:
        return {"continue": False, **public}
    return {"continue": True, "session": new_session.to_dict(), **public}
