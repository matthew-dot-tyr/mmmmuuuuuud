"""Pydantic-схемы запросов и ответов API."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from presets import THEMES

# Фронтенд присылает короткий слаг, движок ждёт человеческое название темы.
# Порядок берём из ai/contracts.py, чтобы не дублировать русский текст.
THEME_BY_SLUG = {
    "work": THEMES[0],       # Работа и карьера
    "money": THEMES[1],      # Деньги и бизнес
    "purchase": THEMES[2],   # Крупные покупки и аренда
    "personal": THEMES[3],   # Быт и личное
}
THEME_SLUGS = tuple(THEME_BY_SLUG)


# --- переговоры ---


class NegotiationStartRequest(BaseModel):
    user_id: str
    theme: Literal[THEME_SLUGS]
    difficulty: int = Field(ge=1, le=3)


class NegotiationTurnRequest(BaseModel):
    user_id: str
    session_token: str = Field(min_length=1, description="то, что вернул предыдущий ответ")
    option_id: Optional[str] = Field(default=None, description="сложность 1-2: выбранный вариант")
    message: Optional[str] = Field(default=None, max_length=2000, description="сложность 3: свободный текст")

    @model_validator(mode="after")
    def require_answer(self):
        if not self.option_id and not (self.message or "").strip():
            raise ValueError("нужен либо option_id, либо непустой message")
        return self


# --- игрок ---


class UserCreateRequest(BaseModel):
    """user_id можно не передавать — тогда сервер сгенерирует его сам."""

    user_id: Optional[str] = None


class UserResponse(BaseModel):
    user_id: str
    xp: int
    level: int
    xp_to_next_level: int
    unlocked_difficulties: list[int]
