"""Тесты подписи состояния переговоров."""

import pytest

import session_token
from session_token import InvalidSessionToken, decode, encode

PAYLOAD = {
    "user_id": "u1",
    "negotiation_id": "n1",
    "session": {"difficulty": 2, "turns_done": 1, "finished": False, "transcript": []},
    "options": [{"option_id": "a", "text": "Вариант"}],
}


def test_roundtrip():
    assert decode(encode(PAYLOAD)) == PAYLOAD


def test_roundtrip_keeps_cyrillic():
    payload = {**PAYLOAD, "session": {"theme": "Работа и карьера"}}
    assert decode(encode(payload))["session"]["theme"] == "Работа и карьера"


def test_rejects_tampered_payload():
    """Подменённые данные без верной подписи не проходят."""
    data, signature = encode(PAYLOAD).split(".")
    with pytest.raises(InvalidSessionToken):
        decode(f"{data}x.{signature}")


def test_rejects_tampered_signature():
    data, signature = encode(PAYLOAD).split(".")
    with pytest.raises(InvalidSessionToken):
        decode(f"{data}.{signature[:-1]}x")


def test_rejects_garbage():
    for bad in ("", "просто строка", "a.b.c", "....", None, 42):
        with pytest.raises(InvalidSessionToken):
            decode(bad)


def test_rejects_token_from_another_secret(monkeypatch):
    """Токен, подписанный другим ключом, не принимается."""
    token = encode(PAYLOAD)
    monkeypatch.setattr(session_token, "SESSION_SECRET", "другой-ключ")
    with pytest.raises(InvalidSessionToken):
        decode(token)


def test_rejects_signed_non_dict(monkeypatch):
    """Даже с верной подписью на вход должен прийти объект, а не список."""
    import json

    payload = json.dumps([1, 2, 3], separators=(",", ":")).encode()
    token = f"{session_token._b64encode(payload)}.{session_token._sign(payload)}"
    with pytest.raises(InvalidSessionToken):
        decode(token)
