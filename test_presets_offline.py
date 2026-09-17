"""
Проверка интерфейса presets.py (то, что реально импортирует main.py), без
API-ключа — ответы Qwen подменяются заготовками. Запуск: python test_presets_offline.py

test_offline.py проверяет внутренний движок (ai/), этот файл — что presets.py
правильно оборачивает его в то, что просил бэкендер: session-as-dict, ключ
"continue" вместо "ends", отсутствие "session" в финальном ответе.
"""
import presets
from ai import llm, dialogue
from ai.contracts import ContractError

answers = []
def fake_chat_json(system, user, temperature=0.7, max_tokens=400, retries=1):
    return answers.pop(0)
llm.chat_json = fake_chat_json
dialogue.random.randint = lambda lo, hi: 2  # детерминированный max_turns для теста

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

# --- PRESETS валиден и проходит validate_request ---
for p in presets.PRESETS:
    assert p["theme"] in presets.THEMES
    assert p["difficulty"] in (1, 2, 3)
print("PRESETS валиден: OK")

# --- start_negotiation: session — dict, есть все публичные поля ---
answers = [{**BASE_START, "options": [opt("Сравнить с рынком"), opt("Согласиться"), opt("Отказаться сразу")]}]
result = presets.start_negotiation("Крупные покупки и аренда", 1, 2)
assert isinstance(result["session"], dict)
assert result["max_turns"] == 2
assert {"scenario_text", "counterpart_opening", "counterpart_role", "counterpart_tone",
        "counterpart_goal", "options"} <= result.keys()
assert all(set(o) == {"option_id", "text"} for o in result["options"])
print("start_negotiation: OK")

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

# --- advance_turn, continue=false: outcome/score/feedback_text есть, session — нет ---
answers = [{"ends": True, "counterpart_reply": "«Хорошо, сойдёмся на 40 000»",
            "outcome": "success", "score": 8, "feedback_text": "Вы удачно оперлись на рыночные данные."}]
turn = presets.advance_turn(session, "40 000 — справедливая середина")
assert turn == {
    "continue": False,
    "counterpart_reply": "«Хорошо, сойдёмся на 40 000»",
    "outcome": "success",
    "score": 8,
    "feedback_text": "Вы удачно оперлись на рыночные данные.",
}
print("advance_turn (continue=false): OK")

# --- calculate_xp доступен напрямую из presets ---
assert presets.calculate_xp("success", 8, 1) == 16
assert presets.calculate_xp("failure", None, 3) == 5
print("calculate_xp: OK")

# --- ошибки пробрасываются как ContractError/AIError, а не тонут молча ---
try:
    presets.start_negotiation("Несуществующая тема", 1, 1)
    raise AssertionError
except ContractError:
    pass
print("ContractError пробрасывается: OK")

print("\nВсе проверки presets.py пройдены.")
