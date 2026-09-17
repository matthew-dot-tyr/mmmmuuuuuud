"""
Публичный интерфейс AI-модуля. Бэкенд импортирует только это:

    from ai import (
        start_negotiation, advance_turn, calculate_xp,
        Session, StartResult, TurnResult, ContractError, AIError, THEMES,
    )
"""
from .contracts import Session, StartResult, TurnResult, ContractError, THEMES
from .llm import AIError
from .dialogue import start_negotiation, advance_turn
from .xp import calculate_xp

__all__ = [
    "start_negotiation", "advance_turn", "calculate_xp",
    "Session", "StartResult", "TurnResult",
    "ContractError", "AIError", "THEMES",
]
