"""
Структуры данных многоходового диалога.

Раунд 0 (start_negotiation): mode ("theme"|"custom"), theme ИЛИ custom_situation,
    difficulty, character_level
    -> либо RejectionResult (сгенерировать сценарий не вышло/не стоит),
    -> либо StartResult: scenario_text, counterpart_opening, counterpart_role/tone/goal
       (options — только на сложности 1-2)

Каждый следующий ход (advance_turn): текущая сессия + сообщение игрока
    -> TurnResult: counterpart_reply, ends
       если ends=False: options для следующего хода (сложность 1-2)
       если ends=True: outcome, score, feedback — итог по всему диалогу.
       feedback — структурный разбор (Feedback: broke_quote/broke_reason/what_worked/
       alternative_phrasing/tip), а если модель дважды не смогла собрать эту структуру —
       деградация до обычной строки (TurnResult.public()["feedback"] тогда просто str,
       а не dict; см. ai/dialogue.py _parse_feedback).

Официального лимита ходов в контракте нет: диалог идёт, пока модель не решит
его закончить (естественная развязка или явно слабый ход игрока). Есть только
скрытый технический потолок SAFETY_MAX_TURNS — это не игровое правило, а защита
от зацикливания/раздувания счёта за API, наружу (фронтенду/бэкенду) он не отдаётся.

Session хранит историю диалога и передаётся туда-обратно между бэкендом
и AI-модулем как обычный dict (см. Session.to_dict/from_dict), поэтому
бэкенд может сохранить его в памяти, в БД, или просто прогонять через фронтенд.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional

THEMES = ("Работа и карьера", "Деньги и бизнес", "Крупные покупки и аренда", "Быт и личное")
DIFFICULTIES = (1, 2, 3)
OUTCOMES = ("success", "failure")
MODES = ("theme", "custom")
REJECTION_REASONS = ("not_a_negotiation", "too_vague", "unsafe")

# Сколько вариантов ответа предлагается на ход на сложностях 1-2. На сложности 3
# вариантов нет — игрок отвечает свободным текстом.
OPTIONS_COUNT = {1: 3, 2: 4}

# Технический (не игровой) потолок ходов игрока за одну сессию — чистая защита от
# зацикливания диалога и неограниченного счёта за API, если модель почему-то никогда
# не решит закончить сама. Держим большим, чтобы он практически никогда не сработал
# в нормальной игре: обычные диалоги должны заканчиваться сами намного раньше.
SAFETY_MAX_TURNS = 20

# Максимальная длина пользовательского описания ситуации в режиме custom (символов).
# 400, а не 1000: так в задании, и validation.py::MAX_LEN должен совпадать с этим
# числом — иначе бэкенд отсечёт раньше, чем сработает эта проверка, и она омертвеет.
CUSTOM_SITUATION_MAX_LEN = 400


class ContractError(ValueError):
    """Данные не соответствуют контракту (в т.ч. ответ модели)."""


def _require_text(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"Поле {name} должно быть непустой строкой, получено: {value!r}")
    return value.strip()


def _optional_text(value) -> Optional[str]:
    """Как _require_text, но None/отсутствие поля — валидное значение (не ошибка),
    а пустая/пробельная строка тоже считается отсутствием значения."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    raise ContractError(f"Ожидалась строка или null, получено: {value!r}")


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


def validate_request(mode: str, theme: Optional[str], custom_situation: Optional[str],
                      difficulty: int, character_level: int) -> None:
    if mode not in MODES:
        raise ContractError(f"mode должен быть 'theme' или 'custom', получено: {mode!r}")
    if mode == "theme":
        if theme not in THEMES:
            raise ContractError(f"Неизвестная тема: {theme!r}. Допустимо: {', '.join(THEMES)}")
    else:
        if not isinstance(custom_situation, str) or not custom_situation.strip():
            raise ContractError("При mode='custom' нужен непустой custom_situation")
        if len(custom_situation) > CUSTOM_SITUATION_MAX_LEN:
            raise ContractError(f"custom_situation длиннее {CUSTOM_SITUATION_MAX_LEN} символов")
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
class RejectionResult:
    """Модель отказалась строить сценарий (актуально только для mode='custom')."""
    reason: str  # одно из REJECTION_REASONS

    def public(self) -> dict:
        return {"rejected": True, "reason": self.reason}


@dataclass
class StartResult:
    scenario_text: str
    counterpart_opening: str
    counterpart_role: str
    counterpart_tone: str
    counterpart_goal: str
    difficulty: int
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
        }
        if self.options is not None:
            data["options"] = [{"option_id": o.option_id, "text": o.text} for o in self.options]
        return data


@dataclass
class Feedback:
    """Структурный разбор диалога судьёй (Фича 2). tip — единственное обязательное
    поле, остальные могут быть None (например, broke_quote/broke_reason/alternative_phrasing
    все null при чистом успехе, где ничего не "ломалось")."""
    tip: str
    broke_quote: Optional[str] = None          # точная цитата реплики ИГРОКА, где пошло не так
    broke_reason: Optional[str] = None         # почему именно эта реплика была проблемой
    what_worked: Optional[str] = None          # что игрок сделал правильно за весь диалог
    alternative_phrasing: Optional[str] = None  # как стоило сформулировать вместо broke_quote

    def public(self) -> dict:
        return {
            "broke_quote": self.broke_quote,
            "broke_reason": self.broke_reason,
            "what_worked": self.what_worked,
            "alternative_phrasing": self.alternative_phrasing,
            "tip": self.tip,
        }


@dataclass
class TurnResult:
    ends: bool
    counterpart_reply: str
    options: Optional[list[TurnOption]] = None          # только если ends=False
    outcome: Optional[str] = None                       # только если ends=True
    score: Optional[int] = None
    feedback: Optional[Feedback] = None                 # структурный разбор, если удался
    feedback_degraded_text: Optional[str] = None        # деградация, если структура не собралась
    # Когда ends=True, ровно одно из feedback / feedback_degraded_text не None.

    def public(self) -> dict:
        data = {"ends": self.ends, "counterpart_reply": self.counterpart_reply}
        if self.ends:
            data["outcome"] = self.outcome
            data["score"] = self.score
            # "feedback" — объект при удачном структурном разборе, иначе обычная строка
            # (деградация). Проверяйте тип на стороне бэкенда/фронтенда: isinstance(..., str).
            data["feedback"] = self.feedback.public() if self.feedback is not None else self.feedback_degraded_text
        elif self.options is not None:
            data["options"] = [{"option_id": o.option_id, "text": o.text} for o in self.options]
        return data


@dataclass
class DialogueTurn:
    speaker: str   # "counterpart" | "player"
    text: str


@dataclass
class Session:
    """Полное состояние переговоров. Хранится между запросами (бэкендом или фронтендом)."""
    theme: Optional[str]
    difficulty: int
    character_level: int
    counterpart_role: str
    counterpart_tone: str
    counterpart_goal: str
    scenario_text: str
    principles_used: list[str]
    turns_done: int = 0          # счётчик для XP/аналитики, НЕ лимит
    finished: bool = False
    transcript: list[DialogueTurn] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Session":
        d = dict(d)
        d["transcript"] = [DialogueTurn(**t) for t in d.get("transcript", [])]
        return cls(**d)
