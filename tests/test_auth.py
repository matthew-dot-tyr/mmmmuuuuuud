"""Тесты auth.get_current_user_id — проверка Supabase JWT напрямую, без
прогона через весь FastAPI-стек (сквозной прогон через приложение — в
tests/test_api.py::test_negotiation_requires_real_bearer_token).

Покрывает обе ветки, которые реально встречаются у Supabase: старый общий
секрет (HS256) и новые асимметричные JWT Signing Keys (ES256, через JWKS) —
на живом токене от Supabase выяснилось, что новые проекты по умолчанию
подписывают именно так, и HS256-only реализация такие токены отвергала.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

import auth as auth_module
from auth import get_current_user_id

# То же значение, что conftest.py кладёт в SUPABASE_JWT_SECRET для тестов.
SECRET = "test-jwt-secret-at-least-32-bytes-long"


def _token(sub="u1", aud="authenticated", exp_delta=3600, secret=SECRET, **extra_claims):
    payload = {"sub": sub, "aud": aud, "exp": time.time() + exp_delta, **extra_claims}
    return jwt.encode(payload, secret, algorithm="HS256")


def test_valid_token_returns_sub():
    assert get_current_user_id(f"Bearer {_token(sub='abc-123')}") == "abc-123"


def test_missing_header_is_401():
    with pytest.raises(HTTPException) as exc:
        get_current_user_id(None)
    assert exc.value.status_code == 401


def test_non_bearer_scheme_is_401():
    with pytest.raises(HTTPException) as exc:
        get_current_user_id("Basic dXNlcjpwYXNz")
    assert exc.value.status_code == 401


def test_empty_bearer_token_is_401():
    with pytest.raises(HTTPException) as exc:
        get_current_user_id("Bearer ")
    assert exc.value.status_code == 401


def test_wrong_secret_is_401():
    """Токен, подписанный не тем ключом (например, чужим проектом), не проходит."""
    token = _token(secret="совсем-другой-секрет")
    with pytest.raises(HTTPException) as exc:
        get_current_user_id(f"Bearer {token}")
    assert exc.value.status_code == 401


def test_expired_token_is_401():
    token = _token(exp_delta=-10)
    with pytest.raises(HTTPException) as exc:
        get_current_user_id(f"Bearer {token}")
    assert exc.value.status_code == 401


def test_wrong_audience_is_401():
    """aud="authenticated" — это токен залогиненного пользователя. Anon-токены
    (aud="anon") к user_id доступа давать не должны."""
    token = _token(aud="anon")
    with pytest.raises(HTTPException) as exc:
        get_current_user_id(f"Bearer {token}")
    assert exc.value.status_code == 401


def test_missing_sub_is_401():
    token = jwt.encode({"aud": "authenticated", "exp": time.time() + 3600}, SECRET, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        get_current_user_id(f"Bearer {token}")
    assert exc.value.status_code == 401


def test_missing_jwt_secret_is_500(monkeypatch):
    """Не настроенный сервер (SUPABASE_JWT_SECRET пуст) — ошибка конфигурации
    (500), а не молчаливое "всем можно" или ошибочный 401."""
    monkeypatch.setattr(auth_module, "SUPABASE_JWT_SECRET", None)
    with pytest.raises(HTTPException) as exc:
        get_current_user_id(f"Bearer {_token()}")
    assert exc.value.status_code == 500


# --- ES256 / JWKS (новые проекты Supabase с асимметричными ключами) ---


class _FakeSigningKey:
    """Заглушка под jwt.PyJWK: реальный код читает только .key."""

    def __init__(self, key):
        self.key = key


def _es256_keypair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key, private_key.public_key()


def _es256_token(private_key, sub="es-user", aud="authenticated", exp_delta=3600, **extra_claims):
    payload = {"sub": sub, "aud": aud, "exp": time.time() + exp_delta, **extra_claims}
    return jwt.encode(payload, private_key, algorithm="ES256")


def test_valid_es256_token_via_jwks_returns_sub(monkeypatch):
    """Сервер не хранит приватный ключ — только достаёт публичный по kid из
    JWKS (тут подменяем сетевой поход своей же тестовой парой ключей)."""
    private_key, public_key = _es256_keypair()
    token = _es256_token(private_key, sub="es-user")

    monkeypatch.setattr(auth_module._jwk_client, "get_signing_key_from_jwt",
                         lambda t: _FakeSigningKey(public_key))
    assert get_current_user_id(f"Bearer {token}") == "es-user"


def test_es256_token_signed_by_wrong_key_is_401(monkeypatch):
    """Токен подписан одним приватным ключом, а JWKS отдаёт публичный от
    другого — подпись не сойдётся, как и должно быть при чужом/поддельном ключе."""
    private_key, _ = _es256_keypair()
    _, other_public_key = _es256_keypair()
    token = _es256_token(private_key)

    monkeypatch.setattr(auth_module._jwk_client, "get_signing_key_from_jwt",
                         lambda t: _FakeSigningKey(other_public_key))
    with pytest.raises(HTTPException) as exc:
        get_current_user_id(f"Bearer {token}")
    assert exc.value.status_code == 401


def test_asymmetric_token_without_jwk_client_is_500(monkeypatch):
    """SUPABASE_URL не настроен -> JWKS-клиент недоступен -> ошибка конфигурации
    сервера (500), а не 401 (это не вина клиента с валидным токеном)."""
    private_key, _ = _es256_keypair()
    token = _es256_token(private_key)

    monkeypatch.setattr(auth_module, "_jwk_client", None)
    with pytest.raises(HTTPException) as exc:
        get_current_user_id(f"Bearer {token}")
    assert exc.value.status_code == 500


def test_unsupported_algorithm_is_401():
    """Ни HS256, ни ES256/RS256 — алгоритм не входит в разрешённый список,
    отклоняем явно, а не пытаемся угадать, как его проверять."""
    token = jwt.encode({"sub": "u1", "aud": "authenticated", "exp": time.time() + 3600},
                        "какой-то-секрет-минимум-48-байт-для-hs384-без-предупреждений",
                        algorithm="HS384")
    with pytest.raises(HTTPException) as exc:
        get_current_user_id(f"Bearer {token}")
    assert exc.value.status_code == 401
