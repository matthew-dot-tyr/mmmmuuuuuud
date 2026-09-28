"""Лимит генераций в час. Кастомные ситуации — прямой вызов платного API
от произвольного текста, без потолка один пользователь сожжёт бюджет
OpenRouter за вечер.
"""

import os

from db import supabase

LIMIT_CUSTOM_PER_USER = int(os.getenv("LIMIT_CUSTOM_PER_USER", "10"))
LIMIT_THEME_PER_USER = int(os.getenv("LIMIT_THEME_PER_USER", "30"))
LIMIT_PER_IP = int(os.getenv("LIMIT_PER_IP", "40"))
LIMIT_TURNS_PER_USER = int(os.getenv("LIMIT_TURNS_PER_USER", "120"))

_warning_shown = False


def _bump(scope: str, key: str, limit: int) -> bool:
    global _warning_shown
    try:
        res = supabase.rpc(
            "check_and_increment_generations",
            {"p_scope": scope, "p_key": str(key), "p_limit": limit},
        ).execute()
        row = res.data[0] if isinstance(res.data, list) else res.data
        return bool(row["allowed"])
    except Exception as e:
        if not _warning_shown:
            _warning_shown = True
            print(f"[warning] Лимит генераций не работает ({e}). "
                  "Накати migrations/003_custom_situations.sql.")
        return True


def allow_generation(user_id: str, mode: str, client_ip: str | None) -> bool:
    limit = LIMIT_CUSTOM_PER_USER if mode == "custom" else LIMIT_THEME_PER_USER
    if not _bump("user", user_id, limit):
        return False
    if client_ip and not _bump("ip", client_ip, LIMIT_PER_IP):
        return False
    return True


def allow_turn(user_id: str) -> bool:
    """Ходы теперь дороже стартов: игрового лимита ходов нет, один диалог
    может занять до SAFETY_MAX_TURNS платных вызовов. Делать только если
    решение 2 не закрылось снижением потолка в движке.
    """
    return _bump("turn", user_id, LIMIT_TURNS_PER_USER)
