"""Единый формат отказа для /negotiation/start.

Отказ — не ошибка сервера. Локальная валидация, лимит и отказ модели
возвращают одну структуру с машиночитаемым кодом. Коды
not_a_negotiation / too_vague / unsafe приходят от модели и заморожены
на созвоне — их знает и API, и фронт.
"""

from enum import Enum


class Mode(str, Enum):
    THEME = "theme"
    CUSTOM = "custom"


class RejectionReason(str, Enum):
    # локальная валидация
    EMPTY = "empty"
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long"
    CONTAINS_LINK = "contains_link"
    GARBAGE = "garbage"
    # лимит
    RATE_LIMITED = "rate_limited"
    # модель
    NOT_A_NEGOTIATION = "not_a_negotiation"
    TOO_VAGUE = "too_vague"
    UNSAFE = "unsafe"


MESSAGES = {
    RejectionReason.EMPTY: "Опишите ситуацию — поле не может быть пустым.",
    RejectionReason.TOO_SHORT: "Опишите ситуацию подробнее — минимум 30 символов.",
    RejectionReason.TOO_LONG: "Слишком длинное описание — максимум 400 символов.",
    RejectionReason.CONTAINS_LINK: "Уберите ссылки из описания.",
    RejectionReason.GARBAGE: "Не получилось разобрать описание. Опишите ситуацию обычным текстом.",
    RejectionReason.RATE_LIMITED: "Вы создали слишком много сценариев за последний час. Попробуйте позже.",
    RejectionReason.NOT_A_NEGOTIATION: "Это не похоже на ситуацию с переговорами. Опишите случай, где нужно о чём-то договориться с другим человеком.",
    RejectionReason.TOO_VAGUE: "Описание слишком общее. Добавьте деталей: с кем вы ведёте переговоры и о чём именно.",
    RejectionReason.UNSAFE: "Не получится построить тренировку на этой ситуации. Попробуйте описать другую.",
}


def rejection(reason: RejectionReason) -> dict:
    """Тело ответа при отказе. HTTP-код при этом 200."""
    return {"rejected": True, "reason": reason.value, "message": MESSAGES[reason]}
