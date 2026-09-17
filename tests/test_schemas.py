"""Тесты контрактов запросов."""

import pytest
from pydantic import ValidationError

from presets import THEMES
from schemas import (
    THEME_BY_SLUG,
    NegotiationStartRequest,
    NegotiationTurnRequest,
    UserCreateRequest,
)


def test_theme_slugs_cover_engine_themes():
    """Слаги API и темы движка должны совпадать один к одному."""
    assert tuple(THEME_BY_SLUG.values()) == tuple(THEMES)


def test_start_request_accepts_known_slugs():
    for slug in THEME_BY_SLUG:
        assert NegotiationStartRequest(user_id="u", theme=slug, difficulty=1).theme == slug


def test_start_request_rejects_unknown_theme():
    with pytest.raises(ValidationError):
        NegotiationStartRequest(user_id="u", theme="готовка", difficulty=1)
    # русское название темы — не слаг, его фронтенд присылать не должен
    with pytest.raises(ValidationError):
        NegotiationStartRequest(user_id="u", theme=THEMES[0], difficulty=1)


def test_start_request_difficulty_range():
    assert NegotiationStartRequest(user_id="u", theme="work", difficulty=3).difficulty == 3
    for bad in (0, 4, 99):
        with pytest.raises(ValidationError):
            NegotiationStartRequest(user_id="u", theme="work", difficulty=bad)


def test_turn_request_needs_option_or_message():
    assert NegotiationTurnRequest(user_id="u", session_token="t", option_id="a").option_id == "a"
    assert NegotiationTurnRequest(user_id="u", session_token="t", message="текст").message == "текст"

    with pytest.raises(ValidationError):
        NegotiationTurnRequest(user_id="u", session_token="t")
    with pytest.raises(ValidationError):
        NegotiationTurnRequest(user_id="u", session_token="t", message="   ")


def test_turn_request_needs_token():
    with pytest.raises(ValidationError):
        NegotiationTurnRequest(user_id="u", session_token="", option_id="a")


def test_user_create_allows_empty_body():
    assert UserCreateRequest().user_id is None
