"""
Пункты 5-6 бэкенд-чеклиста. Нужен настоящий OPENROUTER_API_KEY в .env.
Запуск: python check_quality.py

Часть 1: по одному диалогу на каждую сложность (mode="theme") — смотрим глазами,
         правда ли оппонент на 1 сам хочет договориться, на 2 держится нескольких
         принципов, на 3 почти не уступает. Лимита ходов больше нет — сколько
         реально понадобится ходов, настолько же диалог и растянется.
Часть 2: пример mode="custom" — один текст пользователя, сборка сценария и один
         пример отказа (текст, который не про переговоры).
Часть 3: один и тот же ответ игрока прогоняется через судью N раз — если
         оценка/исход скачут, JUDGE_PROMPT (prompts.py) нужно ужесточить.
"""
import presets


def print_feedback(feedback):
    """feedback — обычно структурный объект (dict с 5 полями), но если модель
    дважды не смогла собрать схему, presets.py отдаёт обычную строку (деградация,
    см. ai/dialogue.py _degrade_feedback_to_text). Печатаем оба случая наглядно,
    чтобы сразу было видно, как часто деградация реально срабатывает на живой модели."""
    if isinstance(feedback, str):
        print("(!) feedback деградировал до простого текста (схема дважды не собралась):")
        print(f"    {feedback}")
        return
    if feedback.get("broke_quote"):
        print(f"  Где сломалось: «{feedback['broke_quote']}»")
        print(f"  Почему: {feedback['broke_reason']}")
    if feedback.get("what_worked"):
        print(f"  Что сработало: {feedback['what_worked']}")
    if feedback.get("alternative_phrasing"):
        print(f"  Как стоило сказать: {feedback['alternative_phrasing']}")
    print(f"  Совет: {feedback['tip']}")


print("=" * 70)
print("ЧАСТЬ 1: пример диалога на каждую сложность (mode=theme)")
print("=" * 70)

for difficulty in (1, 2, 3):
    theme = presets.THEMES[difficulty - 1]
    print(f"\n--- Сложность {difficulty}, тема «{theme}» ---")
    result = presets.start_negotiation("theme", difficulty, character_level=3, theme=theme)
    print(f"Оппонент: {result['counterpart_role']} — {result['counterpart_tone']}")
    print(result["scenario_text"])
    print(f"Оппонент: {result['counterpart_opening']}")

    session = result["session"]
    options = result.get("options")
    turns_used = 0
    while turns_used < 12:  # страховка на случай, если диалог реально не закончится
        turns_used += 1
        if options is None:
            message = ("Смотрите, по этому вопросу у меня есть конкретные цифры и "
                       "аргументы — давайте искать вариант, который устроит нас обоих.")
        else:
            for o in options:
                print(f"  [{o['option_id']}] {o['text']}")
            message = options[0]["text"]  # детерминированный выбор для повторяемости
        print(f"Игрок: {message}")

        result = presets.advance_turn(session, message)
        print(f"Оппонент: {result['counterpart_reply']}")

        if not result["continue"]:
            score_part = f", оценка {result['score']}/10" if result["score"] is not None else ""
            print(f"=== ИТОГ за {turns_used} ход(ов): {result['outcome']}{score_part} ===")
            print_feedback(result["feedback"])
            break
        session, options = result["session"], result.get("options")
    else:
        print(f"(диалог не закончился за {turns_used} ходов — посмотрите глазами, это нормально или зависание)")

print("\n" + "=" * 70)
print("ЧАСТЬ 2: mode=custom — сборка сценария из текста и пример отказа")
print("=" * 70)

print("\n--- Валидная ситуация ---")
result = presets.start_negotiation(
    "custom", difficulty=2, character_level=4,
    custom_situation="Хочу договориться с начальником о переходе на удалёнку 3 дня в неделю",
)
if result.get("rejected"):
    print(f"Неожиданно отклонено: {result['reason']}")
else:
    print(f"Оппонент: {result['counterpart_role']} — {result['counterpart_tone']}")
    print(f"Цель оппонента: {result['counterpart_goal']}")
    print(result["scenario_text"])
    print(f"Оппонент: {result['counterpart_opening']}")

print("\n--- Ожидаемый отказ (текст не про переговоры) ---")
result = presets.start_negotiation(
    "custom", difficulty=1, character_level=1,
    custom_situation="Напиши мне, пожалуйста, короткий анекдот про программистов",
)
print(result if result.get("rejected") else "НЕ отклонено — посмотрите, стоит ли ужесточить CUSTOM_GENERATOR_PROMPT")

print("\n" + "=" * 70)
print("ЧАСТЬ 3: стабильность оценок судьи (один и тот же ответ, N прогонов)")
print("=" * 70)

FIXED_REPLY = ("Смотрите, по этому району аренда в среднем 39-40 тысяч, у меня есть "
               "объявления в подтверждение. Плюс я всегда вовремя плачу и ни разу не "
               "просрочил. Предлагаю 40 000 — это справедливо для нас обоих.")

base = presets.start_negotiation("theme", difficulty=3, character_level=5,
                                  theme="Крупные покупки и аренда")
print(f"Сценарий: {base['scenario_text']}")
print(f"Оппонент: {base['counterpart_opening']}")
print(f"Фиксированный ответ игрока: {FIXED_REPLY}\n")

# Судья теперь решает continue/outcome на КАЖДОМ ходу без привязки к лимиту, так что
# просто прогоняем фиксированный ответ N раз от одного и того же начального состояния
# и смотрим на разброс. "continue": true в части прогонов — тоже валидный результат
# (модель посчитала, что рано подводить итог), это не ошибка сама по себе.
N = 5
outcomes = []
for i in range(N):
    r = presets.advance_turn(base["session"], FIXED_REPLY)
    if r["continue"]:
        outcomes.append(("continue", None))
        print(f"Прогон {i + 1}: continue=true (диалог не завершён)")
    else:
        outcomes.append((r["outcome"], r["score"]))
        print(f"Прогон {i + 1}: {r['outcome']}, score={r['score']}")

unique = set(outcomes)
print(f"\nРазных исходов из {N} прогонов: {len(unique)}")
if len(unique) > 1:
    print("НЕСТАБИЛЬНО — один и тот же ответ дал разные continue/outcome/score. Нужно "
          "ужесточить JUDGE_PROMPT (prompts.py -> ai/prompts.py TURN_SYSTEM): "
          "добавить чёткие критерии и разобрать пример на 3, 6 и 9 баллов.")
else:
    print("Стабильно на этом прогоне.")
