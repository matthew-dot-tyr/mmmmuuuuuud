"""
Проверка многоходового диалога с настоящим Qwen. Нужен файл .env с OPENROUTER_API_KEY.
Запуск: python test_live.py

Печатает время каждого ответа — так сразу видно, помогла ли смена модели/провайдера.
Лимита ходов в контракте нет: диалог идёт, пока модель сама не решит его закончить.
"""
import time
import ai

mode = (input("Режим — theme или custom [theme]: ").strip() or "theme")
difficulty = int(input("Сложность (1/2/3): ").strip() or "1")
level = int(input("Уровень персонажа: ").strip() or "1")

theme = custom_situation = None
if mode == "custom":
    custom_situation = input("Опишите ситуацию своими словами: ").strip()
else:
    theme = input(f"Тема {ai.THEMES}: ").strip() or "Работа и карьера"

t0 = time.perf_counter()
start, session = ai.start_negotiation(mode, difficulty, level, theme=theme, custom_situation=custom_situation)
print(f"[{time.perf_counter() - t0:.1f}с] ответ получен")

if isinstance(start, ai.RejectionResult):
    print(f"\nМодель отказалась строить сценарий. Причина: {start.reason}")
    raise SystemExit

options = start.options  # None на сложности 3

print(f"\nОппонент: {start.counterpart_role} — {start.counterpart_tone}")
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
        print(f"\n=== ИТОГ (ходов игрока: {session.turns_done}): {result.outcome} ===")
        if result.score is not None:
            print(f"Оценка: {result.score}/10")
        if result.feedback is not None:
            fb = result.feedback
            if fb.broke_quote:
                print(f"Где сломалось: «{fb.broke_quote}»")
                print(f"Почему: {fb.broke_reason}")
            if fb.what_worked:
                print(f"Что сработало: {fb.what_worked}")
            if fb.alternative_phrasing:
                print(f"Как стоило сказать: {fb.alternative_phrasing}")
            print(f"Совет: {fb.tip}")
        else:
            print(f"(!) feedback деградировал до текста: {result.feedback_degraded_text}")
        print(f"XP: {ai.calculate_xp(result.outcome, result.score, session.difficulty)}")
        break

    options = result.options  # None на сложности 3, иначе варианты для следующего хода
