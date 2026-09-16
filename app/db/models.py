from sqlalchemy import Column, Integer, String, Text
from app.db.database import Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    opponent_role = Column(String)
    user_role = Column(String)