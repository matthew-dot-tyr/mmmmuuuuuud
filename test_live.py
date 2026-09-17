"""
Проверка многоходового диалога с настоящим Qwen. Нужен файл .env с OPENROUTER_API_KEY.
Запуск: python test_live.py

Печатает время каждого ответа — так сразу видно, помогла ли смена модели/провайдера.
"""
import time
import ai

theme = input(f"Тема {ai.THEMES}: ").strip() or "Работа и карьера"
difficulty = int(input("Сложность (1/2/3): ").strip() or "1")
level = int(input("Уровень персонажа: ").strip() or "1")

t0 = time.perf_counter()
start, session = ai.start_negotiation(theme, difficulty, level)
print(f"[{time.perf_counter() - t0:.1f}с] старт сгенерирован")

options = start.options  # None на сложности 3

print(f"\nПереговоры на {session.max_turns} ход(ов) игрока максимум.")
print(f"Оппонент: {start.counterpart_role} — {start.counterpart_tone}")
print(f"Цель оппонента: {start.counterpart_goal}")
print(f"\n{start.scenario_text}")
print(f"Оппонент: {start.counterpart_opening}")

while True:
    if options is None:
        message = input("\nВаш ответ (свободный текст): ")
    else:
        for o in options:
            print(f"  [{o.option_id}] {o.text}")
        choice = input("Выберите вариант: ").strip()
        chosen = next((o for o in options if o.option_id == choice), None)
        if chosen is None:
            print("Нет такого варианта, попробуйте снова")
            continue
        message = chosen.text

    t0 = time.perf_counter()
    result, session = ai.advance_turn(session, message)
    print(f"[{time.perf_counter() - t0:.1f}с] ответ получен")
    print(f"\nОппонент: {result.counterpart_reply}")

    if result.ends:
        print(f"\n=== ИТОГ: {result.outcome} (ход {session.turns_done} из {session.max_turns} возможных) ===")
        if result.score is not None:
            print(f"Оценка: {result.score}/10")
        print(result.feedback_text)
        print(f"XP: {ai.calculate_xp(result.outcome, result.score, session.difficulty)}")
        break

    options = result.options  # None на сложности 3, иначе варианты для следующего хода
