"""
Проверка логики многоходового диалога без API-ключа: ответы Qwen подменяются
заготовками. Запуск: python test_offline.py
"""
import random
_real_randint = random.randint  # dialogue.random IS the random module, so save this before any monkeypatch

import ai
from ai import dialogue, llm
from ai.contracts import ContractError
from ai.xp import calculate_xp

# ---------------------------------------------------------------
# ai/llm.py: если первая попытка падает (например, у модели скрытое "размышление"
# съело весь max_tokens и JSON обрезался), вторая попытка должна пойти без
# reasoning.enabled=false и с увеличенным max_tokens — проверяем это до того,
# как ниже подменим llm.chat_json целиком заглушкой для остальных тестов.
_request_calls = []
def fake_request(model, system, user, temperature, max_tokens, disable_reasoning):
    _request_calls.append((max_tokens, disable_reasoning))
    if len(_request_calls) == 1:
        raise ValueError("В ответе нет JSON-объекта (симуляция обрезанного ответа)")
    return {"ok": True}
llm._request = fake_request
assert llm.chat_json("sys", "user", max_tokens=400, retries=1) == {"ok": True}
assert len(_request_calls) == 2
assert _request_calls[0] == (400, True)          # первая попытка: reasoning отключаем
assert _request_calls[1][1] is False              # вторая попытка: параметр снят
assert _request_calls[1][0] >= 1200               # и лимит токенов заметно увеличен
print("Восстановление после обрезанного reasoning-ответа: OK")

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
    "principles_used": ["harvard_criteria", "выдуманный_id"],
}
def opt(text):
    return {"text": text}

# ---------------------------------------------------------------
# Сценарий A: сложность 1 (с вариантами), фиксируем max_turns=2
# ---------------------------------------------------------------
import random as _random
dialogue.random.randint = lambda lo, hi: 2  # детерминированное число ходов для теста

answers = [{**BASE_START, "options": [opt("Сравнить с рынком"), opt("Согласиться"), opt("Отказаться сразу")]}]
start, session = ai.start_negotiation("Крупные покупки и аренда", 1, 2)
assert session.max_turns == 2 and session.turns_done == 0
pub = start.public()
assert set(pub) >= {"scenario_text", "counterpart_opening", "counterpart_role", "counterpart_tone", "counterpart_goal", "max_turns", "options"}
assert all(set(o) == {"option_id", "text"} for o in pub["options"])
assert "выдуманный_id" not in start.principles_used
print("Старт (сложность 1): OK")

# Ход 1 из 2: не последний, ends=false с новыми вариантами
answers = [{"ends": False, "counterpart_reply": "«Хорошо, но у меня тоже растут расходы»",
            "options": [opt("Предложить 40 000"), opt("Настоять на 38 000"), opt("Уступить и согласиться на 45 000")]}]
result, session = ai.advance_turn(session, "Средняя цена по району — 39 000, вот объявления")
assert result.ends is False and result.options is not None and len(result.options) == 3
assert session.turns_done == 1 and session.finished is False
assert len(session.transcript) == 3  # opening + player + counterpart
print("Ход 1/2 (не последний): OK")

# Ход 2 из 2: последний -> ends должен быть true. Проверяем, что модель, ошибочно
# вернувшая ends=false, отбраковывается и код делает повторный запрос.
answers = [
    {"ends": False, "counterpart_reply": "болтает дальше"},  # неверно для последнего хода
    {"ends": True, "counterpart_reply": "«Хорошо, сойдёмся на 40 000»",
     "outcome": "success", "score": 8, "feedback_text": "Вы удачно оперлись на рыночные данные."},
]
result, session = ai.advance_turn(session, "40 000 — справедливая middle ground")
assert answers == [], "должен был использовать оба заготовленных ответа (retry)"
assert result.ends is True and result.outcome == "success" and result.score == 8
assert session.finished is True and session.turns_done == 2
print("Ход 2/2 (последний, с retry): OK")

# После finished повторный ход запрещён без обращения к модели
try:
    ai.advance_turn(session, "ещё реплика")
    raise AssertionError("должен был поднять ContractError")
except ContractError:
    pass
print("Запрет хода после завершения: OK")

# ---------------------------------------------------------------
# Сценарий A2: ранний конец при слабом ходе (не дожидаясь max_turns)
# ---------------------------------------------------------------
dialogue.random.randint = lambda lo, hi: 3
answers = [{**BASE_START, "options": [opt("Сравнить с рынком"), opt("Согласиться"), opt("Отказаться сразу")]}]
start, session = ai.start_negotiation("Крупные покупки и аренда", 1, 2)
assert session.max_turns == 3

# Игрок нагрубил на первом же ходу (turns_remaining=3, это НЕ последний ход) —
# модель вправе закончить сразу, код не должен этому мешать.
answers = [{"ends": True, "counterpart_reply": "«Тогда разговор окончен»",
            "outcome": "failure", "score": None, "feedback_text": "Грубость разрушила переговоры."}]
result, session = ai.advance_turn(session, "Да пошли вы, не буду ничего обсуждать")
assert result.ends is True and result.outcome == "failure" and result.score is None
assert session.turns_done == 1 and session.finished is True
print("Ранний конец на слабом ходе (до max_turns): OK")

# ---------------------------------------------------------------
# Сценарий B: сложность 3 (свободный текст), проверяем диапазон ходов и отсутствие options
# ---------------------------------------------------------------
random.seed(0)
dialogue.random.randint = _real_randint

seen_max_turns = set()
for _ in range(20):
    answers = [{**BASE_START}]  # без "options" — difficulty 3 их не запрашивает
    start, session = ai.start_negotiation("Деньги и бизнес", 3, 5)
    seen_max_turns.add(session.max_turns)
    assert "options" not in start.public()
    assert session.max_turns in range(6, 8)
assert seen_max_turns <= {6, 7}
print(f"Диапазон max_turns для сложности 3: {sorted(seen_max_turns)} — OK")

answers = [{"ends": False, "counterpart_reply": "«Продолжаем»"}]
result, session = ai.advance_turn(session, "Свободный текст ответа игрока про критерии сделки")
assert result.ends is False and result.options is None
print("Свободный текст, продолжение диалога: OK")

# ---------------------------------------------------------------
# Контракт 3 (XP) — без изменений
# ---------------------------------------------------------------
assert calculate_xp("failure", None, 3) == 5
assert calculate_xp("success", 10, 3) == 60
assert calculate_xp("success", 4, 1) == 8
for bad in [("success", None, 1), ("success", 11, 1), ("success", 5, 4), ("draw", 5, 1)]:
    try:
        calculate_xp(*bad); raise AssertionError(f"должна быть ошибка: {bad}")
    except ContractError:
        pass
print("Контракт XP: OK")

# ---------------------------------------------------------------
# Неверные входные данные при старте
# ---------------------------------------------------------------
for args in [("Спорт", 1, 1), ("Быт и личное", 4, 1), ("Быт и личное", 1, 0)]:
    try:
        ai.start_negotiation(*args); raise AssertionError(args)
    except ContractError:
        pass
print("Проверка входных данных: OK")

print("\nВсе проверки пройдены.")
