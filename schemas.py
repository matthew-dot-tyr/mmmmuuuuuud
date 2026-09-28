"""Pydantic-схемы запросов и ответов API."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from presets import THEMES
from rejections import Mode

# Фронтенд присылает короткий слаг, движок ждёт человеческое название темы.
# Порядок берём из ai/contracts.py, чтобы не дублировать русский текст.
THEME_BY_SLUG = {
    "work": THEMES[0],       # Работа и карьера
    "money": THEMES[1],      # Деньги и бизнес
    "purchase": THEMES[2],   # Крупные покупки и аренда
    "personal": THEMES[3],   # Быт и личное
}
THEME_SLUGS = tuple(THEME_BY_SLUG)
# Обратный словарь: session["theme"] после /negotiation/start хранит уже
# человеческое название (его ждёт AI-модуль), а не слаг — для логов вроде
# attempts, где нужен слаг (как в negotiations.theme), приходится мапить назад.
THEME_SLUG_BY_NAME = {v: k for k, v in THEME_BY_SLUG.items()}


# --- переговоры ---


class NegotiationStartRequest(BaseModel):
    # user_id сюда не входит: он больше не приходит от клиента, а достаётся
    # из проверенного JWT (см. auth.py::get_current_user_id) — иначе любой
    # мог прислать чужой user_id и получить/испортить чужой прогресс.
    mode: Mode = Mode.THEME
    theme: Optional[Literal[THEME_SLUGS]] = None
    custom_situation: Optional[str] = None
    difficulty: int = Field(ge=1, le=3)

    @model_validator(mode="after")
    def check_mode_fields(self):
        if self.mode is Mode.CUSTOM:
            if self.custom_situation is None:
                raise ValueError("при mode=custom нужно поле custom_situation")
            if self.theme is not None:
                raise ValueError("при mode=custom поле theme недопустимо")
        else:
            if self.theme is None:
                raise ValueError("при mode=theme нужно поле theme")
            if self.custom_situation is not None:
                raise ValueError("при mode=theme поле custom_situation недопустимо")
        return self


class NegotiationTurnRequest(BaseModel):
    # user_id тоже из токена, не из тела — см. комментарий в NegotiationStartRequest.
    session_token: str = Field(min_length=1, description="то, что вернул предыдущий ответ")
    option_id: Optional[str] = Field(default=None, description="сложность 1-2: выбранный вариант")
    message: Optional[str] = Field(default=None, max_length=2000, description="сложность 3: свободный текст")

    @model_validator(mode="after")
    def require_answer(self):
        if not self.option_id and not (self.message or "").strip():
            raise ValueError("нужен либо option_id, либо непустой message")
        return self


# --- игрок ---
#
# Отдельной модели запроса для POST /user больше нет: раньше клиент мог
# передать свой user_id (или получить сгенерированный), теперь id всегда
# берётся из токена (см. routers/users.py), тело запроса не нужно вообще.


class UserResponse(BaseModel):
    user_id: str
    xp: int
    level: int
    xp_to_next_level: int
    unlocked_difficulties: list[int]


# --- лог попыток и стрик ---


class AttemptResponse(BaseModel):
    id: str
    theme: Optional[str]       # null для mode=custom
    level: int                 # сложность сценария (1-3), НЕ уровень персонажа
    success: bool
    score: Optional[int]
    created_at: str


class StreakResponse(BaseModel):
    streak_count: int
    last_practiced_date: Optional[str]
