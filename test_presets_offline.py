"""
Проверка интерфейса presets.py (то, что реально импортирует main.py), без
API-ключа — ответы Qwen подменяются заготовками. Запуск: python test_presets_offline.py

test_offline.py проверяет внутренний движок (ai/), этот файл — что presets.py
правильно оборачивает его в то, что просил бэкендер: session-as-dict, ключ
"continue" вместо "ends", отсутствие "session" в финальном ответе, ветку "rejected"
для mode="custom", и что max_turns нигде наружу не течёт (лимита ходов больше нет).
"""
import presets
from ai import llm
from ai.contracts import ContractError

answers = []
def fake_chat_json(system, user, temperature=0.7, max_tokens=400, retries=1):
    return answers.pop(0)
llm.chat_json = fake_chat_json

BASE_START = {
    "scenario_text": "Вы снимаете квартиру у Игоря.",
    "counterpart_opening": "«С следующего месяца аренда 45 000 вместо 38 000», — говорит Игорь.",
    "counterpart_role": "Арендодатель Игорь, 50 лет",
    "counterpart_tone": "Ссылается на рост цен, тянет время",
    "counterpart_goal": "Поднять аренду как можно выше",
    "principles_used": ["harvard_criteria"],
}
def opt(text):
    return {"text": text}

# --- PRESETS валиден ---
for p in presets.PRESETS:
    assert p["mode"] in presets.MODES
    assert p["theme"] in presets.THEMES
    assert p["difficulty"] in (1, 2, 3)
print("PRESETS валиден: OK")

# --- start_negotiation (mode="theme"): session — dict, все публичные поля, БЕЗ max_turns ---
answers = [{**BASE_START, "options": [opt("Сравнить с рынком"), opt("Согласиться"), opt("Отказаться сразу")]}]
result = presets.start_negotiation("theme", 1, 2, theme="Крупные покупки и аренда")
assert isinstance(result["session"], dict)
assert "max_turns" not in result
assert {"scenario_text", "counterpart_opening", "counterpart_role", "counterpart_tone",
        "counterpart_goal", "options"} <= result.keys()
assert all(set(o) == {"option_id", "text"} for o in result["options"])
print("start_negotiation (theme): OK")

session = result["session"]

# --- advance_turn, continue=true: есть session и options, "ends" наружу не течёт ---
answers = [{"ends": False, "counterpart_reply": "«Хорошо, но у меня тоже растут расходы»",
            "options": [opt("Предложить 40 000"), opt("Настоять на 38 000"), opt("Уступить")]}]
turn = presets.advance_turn(session, "Средняя цена по району — 39 000")
assert turn["continue"] is True
assert "ends" not in turn
assert isinstance(turn["session"], dict)
assert len(turn["options"]) == 3
print("advance_turn (continue=true): OK")

session = turn["session"]

# --- advance_turn, continue=false: outcome/score/feedback (объект) есть, session — нет ---
answers = [{"ends": True, "counterpart_reply": "«Хорошо, сойдёмся на 40 000»",
            "outcome": "success", "score": 8,
            "feedback": {"broke_quote": None, "broke_reason": None,
                         "what_worked": "Вы оперлись на рыночные данные.",
                         "alternative_phrasing": None,
                         "tip": "В следующий раз попробуйте назвать диапазон."}}]
turn = presets.advance_turn(session, "40 000 — справедливая середина")
assert turn == {
    "continue": False,
    "counterpart_reply": "«Хорошо, сойдёмся на 40 000»",
    "outcome": "success",
    "score": 8,
    "feedback": {
        "broke_quote": None, "broke_reason": None,
        "what_worked": "Вы оперлись на рыночные данные.",
        "alternative_phrasing": None,
        "tip": "В следующий раз попробуйте назвать диапазон.",
    },
}
print("advance_turn (continue=false, структурный feedback): OK")

# --- advance_turn: feedback деградировал до строки (схема дважды не собралась) ---
answers = [{**BASE_START}]  # сложность 3 -> без options, один ответ на старт
result = presets.start_negotiation("theme", 3, 1, theme="Быт и личное")

answers = [
    {"ends": True, "counterpart_reply": "«Идёт»", "outcome": "failure", "score": None,
     "feedback": "не объект"},
    {"ends": True, "counterpart_reply": "«Идёт»", "outcome": "failure", "score": None,
     "feedback": "не объект, второй раз"},
]
turn = presets.advance_turn(result["session"], "Реплика игрока")
assert turn["continue"] is False
assert isinstance(turn["feedback"], str) and "второй раз" in turn["feedback"]
print("advance_turn: деградация feedback до строки видна и на уровне presets.py: OK")

# --- start_negotiation (mode="custom"): успех ---
answers = [{**BASE_START, "is_negotiation": True, "options": [opt("a"), opt("b"), opt("c")]}]
result = presets.start_negotiation("custom", 1, 2, custom_situation="Хочу договориться с соседом о шуме")
assert "session" in result and "rejected" not in result
print("start_negotiation (custom, успех): OK")

# --- start_negotiation (mode="custom"): отказ ---
answers = [{"is_negotiation": False, "rejection_reason": "not_a_negotiation"}]
result = presets.start_negotiation("custom", 1, 1, custom_situation="напиши мне стих")
assert result == {"rejected": True, "reason": "not_a_negotiation"}
assert "session" not in result
print("start_negotiation (custom, отказ): OK")

# --- calculate_xp сознательно НЕ экспортируется из presets — единственный источник
# правды по XP это progress.py::calculate_xp_gain (см. README и решение бэкендера 1
# по дублированию формул). ai/xp.py со старой формулой остался только для ручных
# скриптов вроде test_offline.py, presets.py и ai/__init__.py его больше не отдают.
assert not hasattr(presets, "calculate_xp")
print("calculate_xp не течёт из presets (единственный источник — progress.py): OK")

# --- ошибки пробрасываются как ContractError/AIError, а не тонут молча ---
try:
    presets.start_negotiation("theme", 1, 1, theme="Несуществующая тема")
    raise AssertionError
except ContractError:
    pass
print("ContractError пробрасывается: OK")

print("\nВсе проверки presets.py пройдены.")
