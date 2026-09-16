from pydantic import BaseModel


class ScenarioBase(BaseModel):
    title: str
    description: str
    opponent_role: str
    user_role: str


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioResponse(ScenarioBase):
    id: int

    class Config:
        from_attributes = True