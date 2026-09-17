"""Прогресс игрока: уровни, начисление XP, доступ к сложностям.

Тут только чистая логика, без обращений к базе, поэтому файл импортируется
и тестируется без Supabase и без ключей в .env. db.py переэкспортирует
compute_level и xp_to_next_level, чтобы старые скрипты не сломались.
"""

from config import MAX_LEVEL, XP_PER_LEVEL

# Провал всегда даёт фиксированный XP
FAILURE_XP = 5

# Множитель за успех зависит от СЛОЖНОСТИ СЦЕНАРИЯ, а не от уровня игрока
DIFFICULTY_MULTIPLIER = {1: 5, 2: 8, 3: 12}

MIN_SCORE = 1
MAX_SCORE = 10


def compute_level(xp) -> int:
    """level = 1 + floor(xp / XP_PER_LEVEL), но не больше MAX_LEVEL."""
    if xp is None or xp < 0:
        xp = 0
    return min(1 + xp // XP_PER_LEVEL, MAX_LEVEL)


def xp_to_next_level(xp) -> int:
    """Сколько XP осталось до следующего уровня. На максимуме — 0."""
    if xp is None or xp < 0:
        xp = 0
    if compute_level(xp) >= MAX_LEVEL:
        return 0
    return (xp // XP_PER_LEVEL + 1) * XP_PER_LEVEL - xp


def unlocked_difficulties(level: int) -> list:
    """Сложности, доступные игроку этого уровня."""
    return list(range(1, min(max(level, 1), MAX_LEVEL) + 1))


def calculate_xp_gain(result: str, score, difficulty: int) -> int:
    """Сколько XP начислить за один разобранный судьёй сценарий.

    failure -> FAILURE_XP
    success -> score * DIFFICULTY_MULTIPLIER[difficulty]
    """
    if difficulty not in DIFFICULTY_MULTIPLIER:
        raise ValueError(f"Неизвестная сложность: {difficulty}")

    if result != "success":
        return FAILURE_XP

    safe_score = max(MIN_SCORE, min(int(score or 0), MAX_SCORE))
    return safe_score * DIFFICULTY_MULTIPLIER[difficulty]


def can_play_difficulty(level: int, difficulty: int) -> bool:
    """Сложность N открыта только игрокам уровня N и выше."""
    return 1 <= difficulty <= level
