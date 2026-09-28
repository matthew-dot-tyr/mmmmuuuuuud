"""Дешёвые проверки кастомного описания — до обращения к платной модели.

Тут только то, что проверяется без модели: длина, мусор, ссылки. Смысловая
пригодность («это вообще про переговоры?») — задача модели.
"""

import re
from typing import Optional

from rejections import RejectionReason

MIN_LEN = 30
MAX_LEN = 400        # должно совпадать с CUSTOM_SITUATION_MAX_LEN в ai/contracts.py

URL_RE = re.compile(r"(https?://|www\.|\S+\.(ru|com|net|org|io|рф)\b)", re.IGNORECASE)
REPEATED_CHAR_RE = re.compile(r"(.)\1{9,}")
MIN_WORDS = 5
MIN_LETTER_RATIO = 0.5


def validate_custom_situation(text: str) -> Optional[RejectionReason]:
    """Причина отказа или None, если текст прошёл."""
    stripped = (text or "").strip()

    if not stripped:
        return RejectionReason.EMPTY
    if len(stripped) < MIN_LEN:
        return RejectionReason.TOO_SHORT
    if len(stripped) > MAX_LEN:
        return RejectionReason.TOO_LONG
    if URL_RE.search(stripped):
        return RejectionReason.CONTAINS_LINK
    if REPEATED_CHAR_RE.search(stripped):
        return RejectionReason.GARBAGE

    letters = sum(1 for ch in stripped if ch.isalpha())
    if letters / len(stripped) < MIN_LETTER_RATIO:
        return RejectionReason.GARBAGE
    if len(stripped.split()) < MIN_WORDS:
        return RejectionReason.GARBAGE

    return None
