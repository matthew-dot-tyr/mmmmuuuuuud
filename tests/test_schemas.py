"""Тесты контрактов запросов."""

import pytest
from pydantic import ValidationError

from presets import THEMES
from schemas import (
    THEME_BY_SLUG,
    NegotiationStartRequest,
    NegotiationTurnRequest,
)


def test_theme_slugs_cover_engine_themes():
    """Слаги API и темы движка должны совпадать один к одному."""
    assert tuple(THEME_BY_SLUG.values()) == tuple(THEMES)


def test_start_request_has_no_user_id_field():
    """user_id больше не часть тела запроса — он приходит из JWT (auth.py)."""
    assert "user_id" not in NegotiationStartRequest.model_fields
    assert "user_id" not in NegotiationTurnRequest.model_fields


def test_start_request_accepts_known_slugs():
    for slug in THEME_BY_SLUG:
        assert NegotiationStartRequest(theme=slug, difficulty=1).theme == slug


def test_start_request_rejects_unknown_theme():
    with pytest.raises(ValidationError):
        NegotiationStartRequest(theme="готовка", difficulty=1)
    # русское название темы — не слаг, его фронтенд присылать не должен
    with pytest.raises(ValidationError):
        NegotiationStartRequest(theme=THEMES[0], difficulty=1)


def test_start_request_difficulty_range():
    assert NegotiationStartRequest(theme="work", difficulty=3).difficulty == 3
    for bad in (0, 4, 99):
        with pytest.raises(ValidationError):
            NegotiationStartRequest(theme="work", difficulty=bad)


def test_start_request_mode_custom_needs_situation_not_theme():
    with pytest.raises(ValidationError):
        NegotiationStartRequest(mode="custom", difficulty=1)
    with pytest.raises(ValidationError):
        NegotiationStartRequest(mode="custom", theme="work", custom_situation="текст", difficulty=1)


def test_turn_request_needs_option_or_message():
    assert NegotiationTurnRequest(session_token="t", option_id="a").option_id == "a"
    assert NegotiationTurnRequest(session_token="t", message="текст").message == "текст"

    with pytest.raises(ValidationError):
        NegotiationTurnRequest(session_token="t")
    with pytest.raises(ValidationError):
        NegotiationTurnRequest(session_token="t", message="   ")


def test_turn_request_needs_token():
    with pytest.raises(ValidationError):
        NegotiationTurnRequest(session_token="", option_id="a")
