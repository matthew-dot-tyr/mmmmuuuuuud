"""Тесты уровней, формулы XP и блокировки сложности.

Запуск из корня проекта:  pytest -q
"""

import pytest

from progress import (
    DIFFICULTY_MULTIPLIER,
    FAILURE_XP,
    calculate_xp_gain,
    can_play_difficulty,
    compute_level,
    unlocked_difficulties,
    xp_to_next_level,
)


def test_compute_level_boundaries():
    assert compute_level(0) == 1
    assert compute_level(99) == 1
    assert compute_level(100) == 2
    assert compute_level(199) == 2
    assert compute_level(200) == 3
    assert compute_level(1_000_000) == 3
    assert compute_level(-5) == 1
    assert compute_level(None) == 1


def test_xp_to_next_level():
    assert xp_to_next_level(0) == 100
    assert xp_to_next_level(40) == 60
    assert xp_to_next_level(99) == 1
    assert xp_to_next_level(100) == 100
    assert xp_to_next_level(150) == 50
    assert xp_to_next_level(200) == 0      # максимум, дальше расти некуда
    assert xp_to_next_level(999) == 0


def test_unlocked_difficulties():
    assert unlocked_difficulties(1) == [1]
    assert unlocked_difficulties(2) == [1, 2]
    assert unlocked_difficulties(3) == [1, 2, 3]
    assert unlocked_difficulties(99) == [1, 2, 3]


def test_success_multiplier_depends_on_difficulty():
    assert calculate_xp_gain("success", 7, 1) == 35
    assert calculate_xp_gain("success", 7, 2) == 56
    assert calculate_xp_gain("success", 7, 3) == 84


def test_failure_is_fixed():
    assert calculate_xp_gain("failure", None, 1) == FAILURE_XP
    assert calculate_xp_gain("failure", None, 3) == FAILURE_XP
    # даже если модель зачем-то прислала score при провале
    assert calculate_xp_gain("failure", 9, 3) == FAILURE_XP


def test_score_is_clamped():
    assert calculate_xp_gain("success", 15, 1) == 50   # score > 10 -> 10
    assert calculate_xp_gain("success", 0, 1) == 5     # score < 1  -> 1
    assert calculate_xp_gain("success", None, 1) == 5


def test_unknown_difficulty_raises():
    with pytest.raises(ValueError):
        calculate_xp_gain("success", 5, 4)
    with pytest.raises(ValueError):
        calculate_xp_gain("failure", None, 0)


def test_all_difficulties_covered():
    assert set(DIFFICULTY_MULTIPLIER) == {1, 2, 3}


def test_xp_accumulates_across_levels():
    """Проверка п.4 ревью: xp складывается, а не перезатирается константой."""
    xp = 0
    levels = []
    for _ in range(5):
        xp += calculate_xp_gain("success", 9, 1)  # 45 за раз
        levels.append(compute_level(xp))
    assert xp == 225
    assert levels == [1, 1, 2, 2, 3]


def test_difficulty_lock():
    assert can_play_difficulty(1, 1)
    assert not can_play_difficulty(1, 2)
    assert not can_play_difficulty(1, 3)

    assert can_play_difficulty(2, 1)
    assert can_play_difficulty(2, 2)
    assert not can_play_difficulty(2, 3)

    assert can_play_difficulty(3, 3)
    assert not can_play_difficulty(3, 0)
