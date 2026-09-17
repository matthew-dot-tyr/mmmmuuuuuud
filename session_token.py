"""Подпись состояния переговоров.

Сценарии нигде не хранятся: session ходит туда-обратно через клиент. Значит
клиент технически может её подредактировать — например, подставить последний
ход или дописать себе успех. Поэтому наружу уходит не сам dict, а токен:
данные плюс HMAC-подпись. Без ключа сервера подпись не подделать, а сервер
ничего не хранит между запросами.

Токен для клиента — непрозрачная строка: получил в ответе, прислал обратно
следующим запросом как есть.
"""

import base64
import hashlib
import hmac
import json

from config import SESSION_SECRET


class InvalidSessionToken(ValueError):
    """Токен повреждён, подделан или пришёл от другого сервера."""


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except Exception:
        raise InvalidSessionToken("Токен сессии повреждён")


def _sign(payload: bytes) -> str:
    return _b64encode(hmac.new(SESSION_SECRET.encode(), payload, hashlib.sha256).digest())


def encode(session: dict) -> str:
    payload = json.dumps(session, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return f"{_b64encode(payload)}.{_sign(payload)}"


def decode(token: str) -> dict:
    if not isinstance(token, str) or token.count(".") != 1:
        raise InvalidSessionToken("Токен сессии имеет неверный формат")

    data, signature = token.split(".")
    payload = _b64decode(data)

    # compare_digest, чтобы по времени ответа нельзя было подбирать подпись
    if not hmac.compare_digest(_sign(payload), signature):
        raise InvalidSessionToken("Подпись сессии не совпадает")

    try:
        session = json.loads(payload)
    except json.JSONDecodeError:
        raise InvalidSessionToken("Токен сессии повреждён")

    if not isinstance(session, dict):
        raise InvalidSessionToken("Токен сессии повреждён")
    return session
