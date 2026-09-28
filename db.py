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


def log_negotiation(negotiation_id, user_id, mode, theme, custom_situation,
                    difficulty, character_level):
    """Фиксирует начатые переговоры. Нужно для разбора, демо и того,
    чтобы видеть, что люди реально пишут в кастомных ситуациях.
    """
    try:
        supabase.table("negotiations").insert({
            "id": negotiation_id,
            "user_id": user_id,
            "mode": mode,
            "theme": theme,
            "custom_situation": custom_situation,
            "difficulty": difficulty,
            "character_level": character_level,
        }).execute()
    except Exception as e:
        print(f"[warning] Не записаны переговоры {negotiation_id}: {e}")


_attempts_warning_shown = False


def log_attempt(user_id, theme, level, success, score):
    """Лог одной завершённой попытки (успех или провал) — история для игрока
    и материал для стрика. level тут — сложность сценария (1-3), не уровень
    персонажа. Таблица создаётся migrations/004_attempts_streak.sql.
    """
    global _attempts_warning_shown
    try:
        supabase.table("attempts").insert({
            "user_id": user_id,
            "theme": theme,
            "level": level,
            "success": success,
            "score": score,
        }).execute()
    except Exception as e:
        if not _attempts_warning_shown:
            _attempts_warning_shown = True
            print(f"[warning] Таблица attempts недоступна ({e}). "
                  "Накати migrations/004_attempts_streak.sql.")


def get_attempts(user_id, limit=20):
    """Последние попытки игрока, новые сначала.

    Мягкая деградация, как и у остальных таблиц из более поздних миграций
    (negotiations, refusal_log): пока не накатили migrations/004, эндпоинт
    /attempts должен отдавать пустой список, а не ронять страницу игрока 500-кой.
    """
    global _attempts_warning_shown
    try:
        res = supabase.table("attempts").select("*") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        return res.data
    except Exception as e:
        if not _attempts_warning_shown:
            _attempts_warning_shown = True
            print(f"[warning] Таблица attempts недоступна ({e}). "
                  "Накати migrations/004_attempts_streak.sql.")
        return []


_streak_warning_shown = False


def update_user_streak(user_id, streak_count, last_practiced_date):
    """Отдельная функция, а не update_xp: стрик и XP обновляются независимо
    друг от друга и по разным причинам, смешивать их в одном вызове незачем.

    Ошибка тут (например, колонок streak_count/last_practiced_date ещё нет —
    migrations/004 не накатили) не должна ронять весь /negotiation/turn и
    вместе с ним уже посчитанное начисление XP — только логируем и продолжаем,
    как и остальные необязательные side-эффекты в этом файле.
    """
    global _streak_warning_shown
    try:
        supabase.table("users") \
            .update({
                "streak_count": streak_count,
                "last_practiced_date": last_practiced_date.isoformat(),
            }) \
            .eq("id", user_id) \
            .execute()
    except Exception as e:
        if not _streak_warning_shown:
            _streak_warning_shown = True
            print(f"[warning] Не обновлён стрик для {user_id} ({e}). "
                  "Накати migrations/004_attempts_streak.sql.")
