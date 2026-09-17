"""Работа с Supabase: пользователи, XP, уровни."""

from supabase import create_client

from config import require_supabase
# Логика уровней живёт в progress.py (её можно тестировать без базы),
# здесь переэкспортируем для обратной совместимости со скриптами.
from progress import compute_level, xp_to_next_level  # noqa: F401

_url, _key = require_supabase()
supabase = create_client(_url, _key)


def get_user(user_id):
    """Пользователь как dict, либо None если его нет."""
    res = supabase.table("users").select("*").eq("id", user_id).execute()
    if not res.data:
        return None
    return res.data[0]


def get_or_create_user(user_id):
    """Пользователь как dict. Если его нет — создаётся с xp=0, level=1."""
    user = get_user(user_id)
    if user:
        return user

    supabase.table("users") \
        .upsert(
            {"id": user_id, "xp": 0, "level": 1},
            on_conflict="id",
            ignore_duplicates=True,
        ) \
        .execute()

    return get_user(user_id)


def update_xp(user_id, new_xp, new_level):
    """Прямая запись значений. Оставлено для скриптов и ручных правок.

    В обычном потоке начисления используй add_xp: она инкрементит на стороне
    базы и не теряет прогресс при двух одновременных запросах.
    """
    return supabase.table("users") \
        .update({"xp": new_xp, "level": new_level}) \
        .eq("id", user_id) \
        .execute()


_claim_warning_shown = False


def claim_negotiation(negotiation_id, user_id):
    """Помечает переговоры как засчитанные. True — можно начислять XP.

    Нужно потому, что состояние диалога ходит через клиент: без этой проверки
    один и тот же выигрышный ход можно прислать повторно и получать XP снова
    и снова. Таблица создаётся миграцией migrations/002_negotiations.sql.
    """
    global _claim_warning_shown
    try:
        res = supabase.table("finished_negotiations") \
            .insert({"id": negotiation_id, "user_id": user_id}) \
            .execute()
        return bool(res.data)
    except Exception as e:
        message = str(e).lower()
        # Уже засчитано — нарушение уникальности первичного ключа
        if "duplicate" in message or "23505" in message or "already exists" in message:
            return False
        if not _claim_warning_shown:
            _claim_warning_shown = True
            print(
                "[warning] Таблица finished_negotiations недоступна "
                f"({e}). XP начисляется без защиты от повторной отправки — "
                "накати migrations/002_negotiations.sql."
            )
        return True


def add_xp(user_id, gained):
    """Атомарно прибавляет XP и пересчитывает уровень.

    Основной путь — SQL-функция add_xp в Supabase (migrations/001_users.sql).
    Если её ещё не накатили, откатываемся на чтение-запись: работает, но при
    двух одновременных запросах один результат может потеряться.

    Возвращает {"xp": int, "level": int}.
    """
    try:
        res = supabase.rpc("add_xp", {"p_user_id": user_id, "p_gain": gained}).execute()
        row = res.data[0] if isinstance(res.data, list) else res.data
        if row and row.get("xp") is not None:
            return {"xp": row["xp"], "level": row["level"]}
    except Exception:
        # RPC нет или недоступна — используем запасной путь
        pass

    user = get_or_create_user(user_id)
    new_xp = (user["xp"] or 0) + gained
    new_level = compute_level(new_xp)
    update_xp(user_id, new_xp, new_level)
    return {"xp": new_xp, "level": new_level}
