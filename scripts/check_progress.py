"""
Ручная проверка функций прогресса игрока (без сервера).
Запуск из корня проекта:  python -m scripts.check_progress
"""
import uuid

from db import (
    add_xp,
    compute_level,
    get_or_create_user,
    get_user,
    supabase,
    update_xp,
    xp_to_next_level,
)


def check(condition, message):
    if condition:
        print(f"  [OK]   {message}")
    else:
        print(f"  [FAIL] {message}")
        raise SystemExit(1)


def test_compute_level():
    print("compute_level: граничные значения")
    cases = [
        (0, 1),
        (99, 1),
        (100, 2),
        (199, 2),
        (200, 3),
        (299, 3),
        (300, 3),
        (1000, 3),
        (1_000_000, 3),
        (-5, 1),
    ]
    for xp, expected in cases:
        got = compute_level(xp)
        check(got == expected, f"xp={xp} -> level={got} (ожидали {expected})")


def test_xp_to_next_level():
    print("xp_to_next_level")
    cases = [(0, 100), (40, 60), (99, 1), (100, 100), (150, 50), (200, 0), (999, 0)]
    for xp, expected in cases:
        got = xp_to_next_level(xp)
        check(got == expected, f"xp={xp} -> до следующего {got} (ожидали {expected})")


def test_get_or_create_user():
    user_id = str(uuid.uuid4())
    print(f"get_or_create_user: тестовый id {user_id}")

    try:
        # 1. Юзера ещё нет в базе
        check(get_user(user_id) is None, "до вызова юзера в базе нет")

        # 2. Новый юзер создаётся с xp=0, level=1
        user = get_or_create_user(user_id)
        check(str(user["id"]) == user_id, "вернулся юзер с правильным id")
        check(user["xp"] == 0, f"новый юзер: xp={user['xp']} (ожидали 0)")
        check(user["level"] == 1, f"новый юзер: level={user['level']} (ожидали 1)")

        # 3. Повторный вызов не создаёт дубликат
        get_or_create_user(user_id)
        rows = supabase.table("users").select("id").eq("id", user_id).execute().data
        check(len(rows) == 1, f"строк с этим id: {len(rows)} (ожидали 1)")

        # 4. Существующий юзер: функция просто читает, а не сбрасывает в 0
        update_xp(user_id, 150, compute_level(150))
        user = get_or_create_user(user_id)
        check(user["xp"] == 150, f"существующий юзер: xp={user['xp']} (ожидали 150)")
        check(user["level"] == 2, f"существующий юзер: level={user['level']} (ожидали 2)")

        # 5. add_xp прибавляет, а не перезаписывает, и поднимает уровень
        progress = add_xp(user_id, 60)
        check(progress["xp"] == 210, f"после add_xp(60): xp={progress['xp']} (ожидали 210)")
        check(progress["level"] == 3, f"после add_xp(60): level={progress['level']} (ожидали 3)")

        # 6. Значения реально записались в базу, а не только вернулись
        user = get_user(user_id)
        check(user["xp"] == 210, f"в базе xp={user['xp']} (ожидали 210)")
        check(user["level"] == 3, f"в базе level={user['level']} (ожидали 3)")

    finally:
        # Удаляем тестового юзера, даже если проверка упала
        supabase.table("users").delete().eq("id", user_id).execute()
        print("  тестовый юзер удалён")


if __name__ == "__main__":
    test_compute_level()
    print()
    test_xp_to_next_level()
    print()
    test_get_or_create_user()
    print()
    print("Все проверки пройдены.")
