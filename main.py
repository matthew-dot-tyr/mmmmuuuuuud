"""API тренажёра переговоров.

Диалог ведёт AI-модуль (presets.py -> ai/), бэкенд отвечает за игрока:
доступ к сложностям, начисление XP и уровни в Supabase.

Сценарии и историю диалога мы нигде не храним: состояние переговоров уходит
клиенту подписанным токеном и возвращается следующим запросом (session_token.py).
"""

import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.db.database import Base, engine, get_db
from app.db.models import Scenario
from app.schemas.scenario import ScenarioCreate, ScenarioResponse

import session_token
from config import CORS_ORIGINS
from db import add_xp, claim_negotiation, get_or_create_user
from presets import AIError, ContractError, advance_turn, start_negotiation
from progress import calculate_xp_gain, can_play_difficulty, compute_level
from routers import users
from schemas import (
    THEME_BY_SLUG,
    NegotiationStartRequest,
    NegotiationTurnRequest,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Arena Negotiations API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)


@app.get("/")
def read_root():
    return {"message": "Arena Negotiations API is running!"}


# === CRUD сценариев из БД (наследие первой версии, под удаление) ===
@app.get("/scenarios", response_model=list[ScenarioResponse])
def get_scenarios(db: Session = Depends(get_db)):
    return db.query(Scenario).all()


@app.post("/scenarios", response_model=ScenarioResponse)
def create_scenario(scenario: ScenarioCreate, db: Session = Depends(get_db)):
    db_scenario = Scenario(**scenario.model_dump())
    db.add(db_scenario)
    db.commit()
    db.refresh(db_scenario)
    return db_scenario


# === Переговоры ===


def _check_difficulty(level: int, difficulty: int) -> None:
    if not can_play_difficulty(level, difficulty):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Сложность {difficulty} откроется на уровне {difficulty}. "
                f"Ваш уровень: {level}"
            ),
        )


def _pack(user_id: str, negotiation_id: str, session: dict, options) -> str:
    """Подписываем всё, чему нельзя доверять со стороны клиента."""
    return session_token.encode(
        {
            "user_id": user_id,
            "negotiation_id": negotiation_id,
            "session": session,
            "options": options,
        }
    )


@app.post("/negotiation/start")
def negotiation_start(req: NegotiationStartRequest):
    user = get_or_create_user(req.user_id)
    _check_difficulty(user["level"], req.difficulty)

    try:
        result = start_negotiation(
            THEME_BY_SLUG[req.theme], req.difficulty, user["level"]
        )
    except ContractError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AIError:
        raise HTTPException(status_code=503, detail="ИИ временно недоступен, попробуйте ещё раз")

    negotiation_id = str(uuid.uuid4())
    session = result.pop("session")
    return {
        "negotiation_id": negotiation_id,
        "session_token": _pack(req.user_id, negotiation_id, session, result.get("options")),
        **result,
    }


def _resolve_message(options, req: NegotiationTurnRequest) -> str:
    """На сложности 1-2 ответ — только один из выданных вариантов."""
    if options is None:
        if not (req.message or "").strip():
            raise HTTPException(
                status_code=400, detail="На этой сложности нужен свободный текст в поле message"
            )
        return req.message

    chosen = next((o for o in options if o["option_id"] == req.option_id), None)
    if chosen is None:
        allowed = ", ".join(o["option_id"] for o in options)
        raise HTTPException(
            status_code=400,
            detail=f"Неизвестный option_id: {req.option_id!r}. Доступны: {allowed}",
        )
    return chosen["text"]


@app.post("/negotiation/turn")
def negotiation_turn(req: NegotiationTurnRequest):
    try:
        payload = session_token.decode(req.session_token)
    except session_token.InvalidSessionToken as e:
        raise HTTPException(status_code=400, detail=str(e))

    if payload.get("user_id") != req.user_id:
        raise HTTPException(status_code=403, detail="Эти переговоры принадлежат другому игроку")

    session = payload["session"]
    message = _resolve_message(payload.get("options"), req)

    try:
        result = advance_turn(session, message)
    except ContractError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AIError:
        raise HTTPException(status_code=503, detail="ИИ временно недоступен, попробуйте ещё раз")

    # Диалог продолжается — отдаём обновлённый токен
    if result["continue"]:
        new_session = result.pop("session")
        return {
            "session_token": _pack(
                req.user_id, payload["negotiation_id"], new_session, result.get("options")
            ),
            **result,
        }

    # Переговоры закончились: начисляем XP один раз на эти переговоры
    if not claim_negotiation(payload["negotiation_id"], req.user_id):
        raise HTTPException(status_code=409, detail="Эти переговоры уже засчитаны")

    gained = calculate_xp_gain(result["outcome"], result.get("score"), session["difficulty"])
    progress = add_xp(req.user_id, gained)
    level_before = compute_level(progress["xp"] - gained)

    return {
        **result,
        "xp_gained": gained,
        "xp": progress["xp"],
        "level": progress["level"],
        "level_up": progress["level"] > level_before,
    }
