"""API тренажёра переговоров.

Диалог ведёт AI-модуль (presets.py -> ai/), бэкенд отвечает за игрока:
доступ к сложностям, начисление XP и уровни в Supabase.

Сценарии и историю диалога мы нигде не храним: состояние переговоров уходит
клиенту подписанным токеном и возвращается следующим запросом (session_token.py).
"""

import uuid

from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.database import Base, engine, get_db
from app.db.models import Scenario
from app.schemas.scenario import ScenarioCreate, ScenarioResponse

import session_token
from auth import get_current_user_id
from config import CORS_ORIGINS
from db import (
    add_xp,
    claim_negotiation,
    get_or_create_user,
    get_user,
    log_attempt,
    log_negotiation,
    update_user_streak,
)
from presets import AIError, ContractError, advance_turn, start_negotiation
from progress import calculate_xp_gain, can_play_difficulty, compute_level, compute_streak
from rate_limit import allow_generation
from refusal_log import log_ai_error, log_refusal
from rejections import MESSAGES, Mode, RejectionReason, rejection
from routers import users
from schemas import (
    THEME_BY_SLUG,
    THEME_SLUG_BY_NAME,
    NegotiationStartRequest,
    NegotiationTurnRequest,
)
from validation import validate_custom_situation

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


PLAY_PAGE = Path(__file__).parent / "static" / "play.html"


@app.get("/")
def read_root():
    return {"message": "Arena Negotiations API is running!", "play": "/play", "docs": "/docs"}


@app.get("/play", include_in_schema=False)
def play_page():
    """Тестовая веб-страница: пройти переговоры в браузере без фронтенда."""
    if not PLAY_PAGE.exists():
        raise HTTPException(status_code=404, detail="static/play.html не найден")
    return FileResponse(PLAY_PAGE)


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
def negotiation_start(req: NegotiationStartRequest, request: Request,
                       user_id: str = Depends(get_current_user_id)):
    user = get_or_create_user(user_id)
    _check_difficulty(user["level"], req.difficulty)

    client_ip = request.client.host if request.client else None

    if req.mode is Mode.CUSTOM:
        reason = validate_custom_situation(req.custom_situation)
        if reason:
            log_refusal(user_id, req, reason, client_ip=client_ip)
            return rejection(reason)

    if not allow_generation(user_id, req.mode.value, client_ip):
        log_refusal(user_id, req, RejectionReason.RATE_LIMITED, client_ip=client_ip)
        return rejection(RejectionReason.RATE_LIMITED)

    try:
        result = start_negotiation(
            req.mode.value,
            req.difficulty,
            user["level"],
            theme=THEME_BY_SLUG[req.theme] if req.theme else None,
            custom_situation=req.custom_situation,
        )
    except ContractError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AIError as e:
        log_ai_error(user_id, req, str(e), client_ip=client_ip)
        raise HTTPException(status_code=503, detail="ИИ временно недоступен, попробуйте ещё раз")

    if result.get("rejected"):
        reason = RejectionReason(result["reason"])
        log_refusal(user_id, req, reason, client_ip=client_ip)
        return {**result, "message": MESSAGES[reason]}

    negotiation_id = str(uuid.uuid4())
    session = result.pop("session")

    log_negotiation(negotiation_id, user_id, req.mode.value,
                    req.theme, req.custom_situation,
                    req.difficulty, user["level"])

    # контракт выхода не меняется: ни одного нового поля
    return {
        "negotiation_id": negotiation_id,
        "session_token": _pack(user_id, negotiation_id, session, result.get("options")),
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
def negotiation_turn(req: NegotiationTurnRequest, user_id: str = Depends(get_current_user_id)):
    try:
        payload = session_token.decode(req.session_token)
    except session_token.InvalidSessionToken as e:
        raise HTTPException(status_code=400, detail=str(e))

    if payload.get("user_id") != user_id:
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
                user_id, payload["negotiation_id"], new_session, result.get("options")
            ),
            **result,
        }

    # Переговоры закончились: начисляем XP один раз на эти переговоры
    if not claim_negotiation(payload["negotiation_id"], user_id):
        raise HTTPException(status_code=409, detail="Эти переговоры уже засчитаны")

    gained = calculate_xp_gain(result["outcome"], result.get("score"), session["difficulty"])
    progress = add_xp(user_id, gained)
    level_before = compute_level(progress["xp"] - gained)

    # Лог попытки и стрик — из уже подписанной session, а не из тела запроса:
    # клиент не присылает ни theme, ни difficulty на этом эндпоинте, и не должен —
    # это ровно то, что заставило бы снова доверять клиенту (см. auth.py).
    log_attempt(user_id, THEME_SLUG_BY_NAME.get(session.get("theme")), session["difficulty"],
                result["outcome"] == "success", result.get("score"))

    user_row = get_user(user_id) or {}
    new_streak = compute_streak(user_row.get("last_practiced_date"), user_row.get("streak_count"))
    update_user_streak(user_id, new_streak, date.today())

    return {
        **result,
        "xp_gained": gained,
        "xp": progress["xp"],
        "level": progress["level"],
        "level_up": progress["level"] > level_before,
    }
