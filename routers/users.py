"""Эндпоинты пользователя: создание и прогресс.

user_id везде берётся из проверенного JWT (auth.get_current_user_id), а не
из тела/пути запроса — иначе любой мог бы прочитать или испортить чужой
прогресс, просто подставив чужой id.
"""

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user_id
from db import get_attempts, get_or_create_user, get_user
from progress import unlocked_difficulties, xp_to_next_level
from schemas import AttemptResponse, StreakResponse, UserResponse

router = APIRouter(tags=["users"])


def _to_response(user: dict) -> UserResponse:
    xp = user.get("xp") or 0
    level = user.get("level") or 1
    return UserResponse(
        user_id=str(user["id"]),
        xp=xp,
        level=level,
        xp_to_next_level=xp_to_next_level(xp),
        unlocked_difficulties=unlocked_difficulties(level),
    )


@router.post("/user", response_model=UserResponse, status_code=201)
def create_user(user_id: str = Depends(get_current_user_id)):
    """Создаёт профиль текущего (из токена) пользователя, если его ещё нет."""
    user = get_or_create_user(user_id)
    if not user:
        raise HTTPException(status_code=500, detail="Не удалось создать пользователя")
    return _to_response(user)


@router.get("/user/me", response_model=UserResponse)
def read_current_user(user_id: str = Depends(get_current_user_id)):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return _to_response(user)


@router.get("/attempts", response_model=list[AttemptResponse])
def read_attempts(user_id: str = Depends(get_current_user_id)):
    """Последние попытки текущего игрока, новые сначала."""
    return get_attempts(user_id, limit=20)


@router.get("/streak", response_model=StreakResponse)
def read_streak(user_id: str = Depends(get_current_user_id)):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return StreakResponse(
        streak_count=user.get("streak_count") or 0,
        last_practiced_date=user.get("last_practiced_date"),
    )
