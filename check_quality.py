"""
Пункты 5-6 бэкенд-чеклиста. Нужен настоящий OPENROUTER_API_KEY в .env.
Запуск: python check_quality.py

Часть 1: по одному диалогу на каждую сложность — смотрим глазами, правда ли
         оппонент на 1 мягкий, на 2 упирается, на 3 давит, и что число ходов
         укладывается в потолок (2-3 / 4-5 / 6-7).
Часть 2: один и тот же ответ игрока прогоняется через судью N раз на
         ПОСЛЕДНЕМ ходу (когда модель обязана выставить outcome/score) —
         если оценка/исход скачут, JUDGE_PROMPT (prompts.py) нужно ужесточить.
"""
import presets

print("=" * 70)
print("ЧАСТЬ 1: пример диалога на каждую сложность")
print("=" * 70)

for difficulty in (1, 2, 3):
    theme = presets.THEMES[difficulty - 1]
    print(f"\n--- Сложность {difficulty}, тема «{theme}» ---")
    result = presets.start_negotiation(theme, difficulty, character_level=3)
    print(f"Потолок ходов: {result['max_turns']}")
    print(f"Оппонент: {result['counterpart_role']} — {result['counterpart_tone']}")
    print(result["scenario_text"])
    print(f"Оппонент: {result['counterpart_opening']}")

    session = result["session"]
    options = result.get("options")
    turns_used = 0
    while True:
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
            print(result["feedback_text"])
            break
        session, options = result["session"], result.get("options")

print("\n" + "=" * 70)
print("ЧАСТЬ 2: стабильность оценок судьи (один и тот же ответ, N прогонов)")
print("=" * 70)

FIXED_REPLY = ("Смотрите, по этому району аренда в среднем 39-40 тысяч, у меня есть "
               "объявления в подтверждение. Плюс я всегда вовремя плачу и ни разу не "
               "просрочил. Предлагаю 40 000 — это справедливо для нас обоих.")

base = presets.start_negotiation("Крупные покупки и аренда", difficulty=3, character_level=5)
print(f"Сценарий: {base['scenario_text']}")
print(f"Оппонент: {base['counterpart_opening']}")
print(f"Фиксированный ответ игрока: {FIXED_REPLY}\n")

# Принудительно делаем этот ход последним (turns_remaining=1), чтобы модель
# каждый раз была ОБЯЗАНА выставить outcome/score, а не иногда продолжать
# диалог — так измеряем чистую нестабильность оценки, а не решения continue.
forced_final_session = dict(base["session"], max_turns=base["session"]["turns_done"] + 1)

N = 5
outcomes = []
for i in range(N):
    r = presets.advance_turn(forced_final_session, FIXED_REPLY)
    outcomes.append((r["outcome"], r["score"]))
    print(f"Прогон {i + 1}: {r['outcome']}, score={r['score']}")

unique = set(outcomes)
print(f"\nРазных исходов из {N} прогонов: {len(unique)}")
if len(unique) > 1:
    print("НЕСТАБИЛЬНО — один и тот же ответ дал разные outcome/score. Нужно "
          "ужесточить JUDGE_PROMPT (prompts.py -> ai/prompts.py TURN_SYSTEM): "
          "добавить чёткие критерии и разобрать пример на 3, 6 и 9 баллов.")
else:
    print("Стабильно на этом прогоне.")
