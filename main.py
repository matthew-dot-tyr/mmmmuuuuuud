import os
import json
import random
import requests
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from dotenv import load_dotenv

from app.db.database import engine, Base, get_db
from app.db.models import Scenario
from app.schemas.scenario import ScenarioCreate, ScenarioResponse

from presets import PRESETS
from prompts import GENERATOR_PROMPT, JUDGE_PROMPT

try:
    from db import update_xp
except ImportError:
    update_xp = None

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Arena Negotiations API")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# Pydantic-схемы для LLM
class ScenarioRequest(BaseModel):
    level: int = 1


class JudgeRequest(BaseModel):
    user_id: str
    scenario: str
    opponent_line: str
    user_reply: str


# Вспомогательная функция отправки запроса в OpenRouter
def ask_llm(prompt: str) -> dict:
    if not OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=500, detail="OPENROUTER_API_KEY не найден в .env"
        )

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={
            "model": "qwen/qwen-turbo",
            "messages": [{"role": "user", "content": prompt}],
        },
    )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Ошибка запроса к ИИ")

    content = response.json()["choices"][0]["message"]["content"]
    cleaned_content = content.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned_content)


@app.get("/")
def read_root():
    return {"message": "Arena Negotiations API is running!"}


# === CRUD сценариев из БД ===
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


# === Эндпоинты ИИ (LLM) ===
@app.post("/scenario")
def generate_scenario(req: ScenarioRequest):
    matching_presets = [p for p in PRESETS if p["level"] == req.level]
    preset = (
        random.choice(matching_presets) if matching_presets else PRESETS[0]
    )

    prompt = GENERATOR_PROMPT.format(**preset)
    return ask_llm(prompt)


@app.post("/judge")
def judge_negotiation(req: JudgeRequest):
    prompt = JUDGE_PROMPT.format(
        scenario=req.scenario,
        opponent_line=req.opponent_line,
        user_reply=req.user_reply,
    )
    result = ask_llm(prompt)

    if result.get("status") == "success" and update_xp:
        update_xp(user_id=req.user_id, new_xp=100, new_level=2)

    return result