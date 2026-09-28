"""
Проверка логики многоходового диалога без API-ключа: ответы Qwen подменяются
заготовками. Запуск: python test_offline.py

Лимита ходов в контракте больше нет — диалог идёт, пока модель не решит его
закончить. Есть только скрытый технический потолок SAFETY_MAX_TURNS (защита от
зацикливания), он проверяется отдельно и не виден ни в одном публичном ответе.
"""
from dataclasses import replace as dc_replace

import ai
from ai import dialogue, llm
from ai.contracts import ContractError, SAFETY_MAX_TURNS
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
# Сценарий A: mode="theme", сложность 1 (с вариантами) — max_turns в контракте нет,
# диалог продолжается сколько нужно и заканчивается только решением модели.
# ---------------------------------------------------------------
answers = [{**BASE_START, "options": [opt("Сравнить с рынком"), opt("Согласиться"), opt("Отказаться сразу")]}]
start, session = ai.start_negotiation("theme", 1, 2, theme="Крупные покупки и аренда")
pub = start.public()
assert set(pub) == {"scenario_text", "counterpart_opening", "counterpart_role",
                     "counterpart_tone", "counterpart_goal", "options"}
assert "max_turns" not in pub
assert all(set(o) == {"option_id", "text"} for o in pub["options"])
assert "выдуманный_id" not in start.principles_used
assert session.turns_done == 0 and session.finished is False
print("Старт (theme, сложность 1): OK")

# Три хода подряд продолжаются — никакого форсирования на "последнем" ходу, потому что
# такого понятия больше нет.
for i in range(3):
    answers = [{"ends": False, "counterpart_reply": f"«Ход {i}»",
                "options": [opt("Предложить 40 000"), opt("Настоять на 38 000"), opt("Уступить")]}]
    result, session = ai.advance_turn(session, f"Реплика игрока {i}")
    assert result.ends is False and result.options is not None
    assert session.turns_done == i + 1 and session.finished is False
print("Диалог продолжается сколько нужно, без принудительного конца: OK")

# Модель сама решает закончить — код это принимает без вопросов. Структурный разбор
# (Фича 2) собирается полностью, включая необязательные поля.
answers = [{"ends": True, "counterpart_reply": "«Хорошо, сойдёмся на 40 000»",
            "outcome": "success", "score": 8,
            "feedback": {"broke_quote": None, "broke_reason": None,
                         "what_worked": "Вы оперлись на рыночные цены, а не на эмоции.",
                         "alternative_phrasing": None,
                         "tip": "В следующий раз можно сразу предложить диапазон, а не одно число."}}]
result, session = ai.advance_turn(session, "40 000 — справедливая середина")
assert result.ends is True and result.outcome == "success" and result.score == 8
assert session.finished is True
assert result.feedback.tip.startswith("В следующий раз")
assert result.feedback.broke_quote is None  # чистый успех — ломаться было нечему
pub = result.public()
assert isinstance(pub["feedback"], dict)
assert set(pub["feedback"]) == {"broke_quote", "broke_reason", "what_worked", "alternative_phrasing", "tip"}
print("Структурный разбор (Фича 2) при успехе: OK")

# После finished повторный ход запрещён без обращения к модели
try:
    ai.advance_turn(session, "ещё реплика")
    raise AssertionError("должен был поднять ContractError")
except ContractError:
    pass
print("Запрет хода после завершения: OK")

# ---------------------------------------------------------------
# Сценарий A2: ранний конец при слабом ходе — это по-прежнему решение модели,
# просто раньше, чем в предыдущем сценарии, и код не мешает этому случиться.
# ---------------------------------------------------------------
answers = [{**BASE_START, "options": [opt("Сравнить с рынком"), opt("Согласиться"), opt("Отказаться сразу")]}]
start, session = ai.start_negotiation("theme", 1, 2, theme="Крупные покупки и аренда")

answers = [{"ends": True, "counterpart_reply": "«Тогда разговор окончен»",
            "outcome": "failure", "score": None,
            "feedback": {"broke_quote": "Да пошли вы, не буду ничего обсуждать",
                         "broke_reason": "Грубость разрушила переговоры вместо того, чтобы их вести.",
                         "what_worked": None,
                         "alternative_phrasing": "Мне некомфортна эта сумма, давайте обсудим, откуда она взялась.",
                         "tip": "Даже при несогласии оставайтесь в диалоге, а не хлопайте дверью."}}]
result, session = ai.advance_turn(session, "Да пошли вы, не буду ничего обсуждать")
assert result.ends is True and result.outcome == "failure" and result.score is None
assert session.turns_done == 1 and session.finished is True
assert result.feedback.broke_quote == "Да пошли вы, не буду ничего обсуждать"
assert result.feedback.alternative_phrasing is not None
print("Структурный разбор (Фича 2) при провале, с цитатой: OK")

# ---------------------------------------------------------------
# Технический потолок SAFETY_MAX_TURNS: не игровой лимит, а аварийная защита от
# зацикливания. Проверяем на самом краю — модель, ошибочно продолжившая диалог,
# должна быть отбракована (ContractError -> retry), а не тихо принята.
# ---------------------------------------------------------------
answers = [{**BASE_START, "options": [opt("a"), opt("b"), opt("c")]}]
start, session = ai.start_negotiation("theme", 1, 2, theme="Крупные покупки и аренда")
edge_session = dc_replace(session, turns_done=SAFETY_MAX_TURNS - 1)

answers = [
    {"ends": False, "counterpart_reply": "тянет ещё"},  # недопустимо на грани потолка
    {"ends": True, "counterpart_reply": "«На этом закончим»",
     "outcome": "failure", "score": None,
     "feedback": {"broke_quote": None, "broke_reason": None, "what_worked": None,
                  "alternative_phrasing": None, "tip": "Переговоры затянулись без результата."}},
]
result, edge_session = ai.advance_turn(edge_session, "ещё одна реплика")
assert answers == [], "должен был использовать оба заготовленных ответа (retry)"
assert result.ends is True
print("Технический потолок SAFETY_MAX_TURNS форсирует конец (не виден игроку): OK")

# ---------------------------------------------------------------
# Фича 2, деградация: строгая схема feedback дважды не собралась (модель прислала
# что-то не по формату) — на первой попытке это ContractError (retry), а на второй,
# последней, попытке код не должен ронять весь ход ошибкой: feedback деградирует
# до обычной строки, но ends/outcome/score всё равно доходят до игрока.
# ---------------------------------------------------------------
answers = [{**BASE_START, "options": [opt("a"), opt("b"), opt("c")]}]
start, session = ai.start_negotiation("theme", 2, 3, theme="Деньги и бизнес")

answers = [
    {"ends": True, "counterpart_reply": "«Договорились»", "outcome": "success", "score": 6,
     "feedback": "просто строка вместо объекта — модель сломала схему"},   # 1-я попытка: невалидно, retry
    {"ends": True, "counterpart_reply": "«Договорились»", "outcome": "success", "score": 6,
     "feedback": "просто строка вместо объекта — модель сломала схему ещё раз"},  # 2-я (последняя): деградация
]
result, session = ai.advance_turn(session, "Финальное предложение игрока")
assert answers == [], "должен был использовать оба заготовленных ответа"
assert result.ends is True and result.outcome == "success" and result.score == 6
assert result.feedback is None  # структуру собрать не вышло
pub = result.public()
assert isinstance(pub["feedback"], str)  # деградация: строка, а не объект
assert "ещё раз" in pub["feedback"]
print("Фича 2, деградация feedback до простого текста после неудачного retry: OK")

# ---------------------------------------------------------------
# Сценарий B: mode="theme", сложность 3 (свободный текст) — options не запрашиваются.
# ---------------------------------------------------------------
answers = [{**BASE_START}]
start, session = ai.start_negotiation("theme", 3, 5, theme="Деньги и бизнес")
assert "options" not in start.public()

answers = [{"ends": False, "counterpart_reply": "«Продолжаем»"}]
result, session = ai.advance_turn(session, "Свободный текст ответа игрока про критерии сделки")
assert result.ends is False and result.options is None
print("Свободный текст, продолжение диалога: OK")

# ---------------------------------------------------------------
# Сценарий C: mode="custom" — успешная сборка сценария из текста пользователя.
# ---------------------------------------------------------------
CUSTOM_BASE = {**BASE_START, "is_negotiation": True}
answers = [{**CUSTOM_BASE, "options": [opt("a"), opt("b"), opt("c")]}]
start, session = ai.start_negotiation("custom", 1, 2, custom_situation="Хочу договориться с соседом о шуме по вечерам")
assert isinstance(start, ai.StartResult)
assert session is not None
print("custom: валидная ситуация собирается в сценарий: OK")

# ---------------------------------------------------------------
# Сценарий D: mode="custom" — отказ (слишком расплывчато).
# ---------------------------------------------------------------
answers = [{"is_negotiation": False, "rejection_reason": "too_vague"}]
start, session = ai.start_negotiation("custom", 1, 1, custom_situation="деньги")
assert isinstance(start, ai.RejectionResult)
assert session is None
assert start.public() == {"rejected": True, "reason": "too_vague"}
print("custom: отказ (too_vague) корректно распознаётся: OK")

# Неверный код причины от модели отбраковывается и код делает повторный запрос.
answers = [
    {"is_negotiation": False, "rejection_reason": "какая-то отсебятина"},
    {"is_negotiation": False, "rejection_reason": "unsafe"},
]
start, session = ai.start_negotiation("custom", 1, 1, custom_situation="что-то")
assert answers == []
assert start.reason == "unsafe"
print("custom: неверный rejection_reason отбраковывается (retry): OK")

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
bad_requests = [
    dict(mode="theme", difficulty=1, character_level=1, theme="Спорт"),               # неизвестная тема
    dict(mode="theme", difficulty=4, character_level=1, theme="Быт и личное"),        # сложность вне диапазона
    dict(mode="theme", difficulty=1, character_level=0, theme="Быт и личное"),        # уровень < 1
    dict(mode="custom", difficulty=1, character_level=1, custom_situation=""),        # пустой custom_situation
    dict(mode="custom", difficulty=1, character_level=1, custom_situation="x" * 2000),  # слишком длинно
    dict(mode="weird", difficulty=1, character_level=1),                              # неизвестный mode
]
for kwargs in bad_requests:
    try:
        ai.start_negotiation(**kwargs)
        raise AssertionError(kwargs)
    except ContractError:
        pass
print("Проверка входных данных: OK")

print("\nВсе проверки пройдены.")
