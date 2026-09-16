from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import engine, Base, get_db
from app.db.models import Scenario
from app.schemas.scenario import ScenarioCreate, ScenarioResponse

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Arena Negotiations API")


@app.get("/")
def read_root():
    return {"message": "Arena Negotiations API is running!"}


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