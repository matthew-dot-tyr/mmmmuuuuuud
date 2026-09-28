"""
Публичный интерфейс AI-модуля. Бэкенд импортирует только это:

    from ai import (
        start_negotiation, advance_turn,
        Session, StartResult, TurnResult, RejectionResult,
        ContractError, AIError, THEMES, MODES,
    )

calculate_xp (ai/xp.py) сознательно не экспортируется отсюда: он жил в двух
формулах одновременно с progress.py::calculate_xp_gain, и продакшен-код мог
случайно взять не ту. Единственный источник правды для начисления XP —
progress.py. ai/xp.py файл не удалён — его прямо использует ручной скрипт
test_offline.py (`from ai.xp import calculate_xp`) для проверки движка в
изоляции от бэкенда.
"""
from .contracts import Session, StartResult, TurnResult, RejectionResult, ContractError, THEMES, MODES
from .llm import AIError
from .dialogue import start_negotiation, advance_turn

__all__ = [
    "start_negotiation", "advance_turn",
    "Session", "StartResult", "TurnResult", "RejectionResult",
    "ContractError", "AIError", "THEMES", "MODES",
]
