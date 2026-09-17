"""Контракт 3: формула опыта. Чистая функция без AI."""
from .contracts import DIFFICULTIES, ContractError, _check_score

FAILURE_XP = 5


def calculate_xp(outcome: str, score, difficulty: int) -> int:
    if difficulty not in DIFFICULTIES:
        raise ContractError(f"difficulty должен быть 1, 2 или 3, получено: {difficulty!r}")
    score = _check_score(outcome, score)
    if outcome == "failure":
        return FAILURE_XP
    return score * difficulty * 2
