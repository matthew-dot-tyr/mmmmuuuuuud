"""Лог отказов: и локальных, и модельных.

На приёмке по этому логу видно, где модель отказывает зря — значит промпт
слишком строгий, — а где фильтр работает правильно.
"""

from db import supabase
from rejections import RejectionReason

_warning_shown = False


def _insert(row: dict) -> None:
    global _warning_shown
    try:
        supabase.table("refusal_log").insert(row).execute()
    except Exception as e:
        if not _warning_shown:
            _warning_shown = True
            print(f"[warning] refusal_log недоступен ({e}). "
                  "Накати migrations/003_custom_situations.sql.")


def log_refusal(user_id: str, req, reason: RejectionReason, raw: str = "",
                client_ip: str | None = None) -> None:
    # user_id — отдельный параметр, а не req.user_id: тело запроса больше не
    # содержит user_id (он приходит из проверенного JWT, см. auth.py).
    _insert({
        "user_id": user_id,
        "client_ip": client_ip,
        "mode": req.mode.value,
        "reason": reason.value,
        "input_text": req.custom_situation or req.theme,
        "raw_response": raw[:2000] if raw else None,
        "difficulty": req.difficulty,
    })


def log_ai_error(user_id: str, req, error: str, client_ip: str | None = None) -> None:
    """Недоступность модели — не отказ, но в том же логе: иначе на приёмке
    непонятно, сколько попыток вообще не дошло до модели.
    """
    _insert({
        "user_id": user_id,
        "client_ip": client_ip,
        "mode": req.mode.value,
        "reason": "ai_error",
        "input_text": req.custom_situation or req.theme,
        "raw_response": error[:2000],
        "difficulty": req.difficulty,
    })
