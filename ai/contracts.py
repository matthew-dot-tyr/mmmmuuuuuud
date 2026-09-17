"""
Структуры данных многоходового диалога.

Раунд 0 (start_negotiation): theme, difficulty, character_level
    -> StartResult: scenario_text, counterpart_opening, counterpart_role/tone/goal,
       max_turns, options (только на сложности 1-2)

Каждый следующий ход (advance_turn): текущая сессия + сообщение игрока
    -> TurnResult: counterpart_reply, ends
       если ends=False: options для следующего хода (сложность 1-2)
       если ends=True: outcome, score, feedback_text — итог по всему диалогу

Session хранит историю диалога и передаётся туда-обратно между бэкендом
и AI-модулем как обычный dict (см. Session.to_dict/from_dict), поэтому
бэкенд может сохранить его в памяти или в БД между HTTP-запросами.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional

THEMES = ("Работа и карьера", "Деньги и бизнес", "Крупные покупки и аренда", "Быт и личное")
DIFFICULTIES = (1, 2, 3)
OUTCOMES = ("success", "failure")

# Сколько ходов игрока (реплик с его стороны) допускается на каждой сложности.
# Реальное число выбирается случайно в этом диапазоне при старте сессии.
TURNS_RANGE = {1: (2, 3), 2: (4, 5), 3: (6, 7)}

# Сколько вариантов ответа предлагается на ход на сложностях 1-2. На сложности 3
# вариантов нет — игрок отвечает свободным текстом.
OPTIONS_COUNT = {1: 3, 2: 4}


class ContractError(ValueError):
    """Данные не соответствуют контракту (в т.ч. ответ модели)."""


def _require_text(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"Поле {name} должно быть непустой строкой, получено: {value!r}")
    return value.strip()


def _to_bool(value, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise ContractError(f"Поле {name} должно быть true/false, получено: {value!r}")


def _check_score(outcome: str, score) -> Optional[int]:
    if outcome not in OUTCOMES:
        raise ContractError(f"outcome должен быть success или failure, получено: {outcome!r}")
    if outcome == "failure":
        return None
    try:
        score = int(score)
    except (TypeError, ValueError):
        raise ContractError("При outcome=success поле score обязательно")
    if not 1 <= score <= 10:
        raise ContractError(f"score должен быть от 1 до 10, получено: {score}")
    return score


def validate_request(theme, difficulty, character_level) -> None:
    if theme not in THEMES:
        raise ContractError(f"Неизвестная тема: {theme!r}. Допустимо: {', '.join(THEMES)}")
    if difficulty not in DIFFICULTIES:
        raise ContractError(f"difficulty должен быть 1, 2 или 3, получено: {difficulty!r}")
    if not isinstance(character_level, int) or character_level < 1:
        raise ContractError("character_level должен быть целым числом от 1")


@dataclass
class TurnOption:
    option_id: str
    text: str


def _parse_options(raw, difficulty: int) -> Optional[list[TurnOption]]:
    """На сложности 3 вариантов нет (свободный текст). На 1-2 их 3-4, без скрытой оценки —
    правильность хода определяется моделью по всему диалогу в конце, а не по отдельному варианту."""
    if difficulty == 3:
        return None
    if not isinstance(raw, list) or not (3 <= len(raw) <= 4):
        raise ContractError("На сложности 1-2 нужно 3-4 варианта ответа")
    options = []
    for i, o in enumerate(raw):
        text = _require_text(o.get("text") if isinstance(o, dict) else None, "options.text")
        options.append(TurnOption(option_id=chr(ord("a") + i), text=text))
    return options


@dataclass
class StartResult:
    scenario_text: str
    counterpart_opening: str
    counterpart_role: str
    counterpart_tone: str
    counterpart_goal: str
    difficulty: int
    max_turns: int
    principles_used: list[str]
    options: Optional[list[TurnOption]] = None

    def public(self) -> dict:
        """То, что уходит фронтенду при старте сессии."""
        data = {
            "scenario_text": self.scenario_text,
            "counterpart_opening": self.counterpart_opening,
            "counterpart_role": self.counterpart_role,
            "counterpart_tone": self.counterpart_tone,
            "counterpart_goal": self.counterpart_goal,
            "max_turns": self.max_turns,
        }
        if self.options is not None:
            data["options"] = [{"option_id": o.option_id, "text": o.text} for o in self.options]
        return data


@dataclass
class TurnResult:
    ends: bool
    counterpart_reply: str
    options: Optional[list[TurnOption]] = None          # только если ends=False
    outcome: Optional[str] = None                       # только если ends=True
    score: Optional[int] = None
    feedback_text: Optional[str] = None

    def public(self) -> dict:
        data = {"ends": self.ends, "counterpart_reply": self.counterpart_reply}
        if self.ends:
            data["outcome"] = self.outcome
            data["score"] = self.score
            data["feedback_text"] = self.feedback_text
        elif self.options is not None:
            data["options"] = [{"option_id": o.option_id, "text": o.text} for o in self.options]
        return data


@dataclass
class DialogueTurn:
    speaker: str   # "counterpart" | "player"
    text: str


@dataclass
class Session:
    """Полное состояние переговоров. Хранится на бэкенде между запросами."""
    theme: str
    difficulty: int
    character_level: int
    counterpart_role: str
    counterpart_tone: str
    counterpart_goal: str
    scenario_text: str
    principles_used: list[str]
    max_turns: int
    turns_done: int = 0          # сколько сообщений игрока уже было
    finished: bool = False
    transcript: list[DialogueTurn] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        d = dict(d)
        d["transcript"] = [DialogueTurn(**t) for t in d.get("transcript", [])]
        return cls(**d)

    def turns_remaining(self) -> int:
        return self.max_turns - self.turns_done
