"""Эндпоинты пользователя: создание и прогресс."""

import uuid

from fastapi import APIRouter, HTTPException

from db import get_or_create_user, get_user
from progress import unlocked_difficulties, xp_to_next_level
from schemas import UserCreateRequest, UserResponse

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
def create_user(req: UserCreateRequest):
    user_id = req.user_id or str(uuid.uuid4())
    user = get_or_create_user(user_id)
    if not user:
        raise HTTPException(status_code=500, detail="Не удалось создать пользователя")
    return _to_response(user)


@router.get("/user/{user_id}", response_model=UserResponse)
def read_user(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return _to_response(user)
