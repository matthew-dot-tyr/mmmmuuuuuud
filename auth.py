"""Проверка JWT от Supabase Auth (magic link, без пароля).

user_id ниоткуда, кроме этого файла, в приложение не попадает: раньше клиент
присылал user_id прямым полем в теле запроса — любой мог подставить чужой id
и читать/портить чужой прогресс. Теперь user_id — это claim "sub" из
подписанного токена, который выдаёт Supabase Auth после входа по magic link,
и подделать его без ключа проверки нельзя.

Supabase подписывает токены одним из двух способов в зависимости от проекта:
  - старые проекты (или явно оставленные на "Legacy JWT Secret") — HS256,
    общий секрет, SUPABASE_JWT_SECRET из дашборда;
  - новые проекты по умолчанию — асимметричные JWT Signing Keys (ES256/RS256):
    подписывается приватным ключом, который серверу знать не нужно, проверка —
    публичным ключом с {SUPABASE_URL}/auth/v1/.well-known/jwks.json (кэшируется
    PyJWKClient, ключи там ротируются самим Supabase, а не нами).
Смотрим alg в заголовке токена и идём по соответствующей ветке, а не гадаем.

Использование в эндпоинте:

    from auth import get_current_user_id

    @app.post("/что-то")
    def handler(user_id: str = Depends(get_current_user_id)):
        ...
"""

import jwt
from fastapi import Header, HTTPException

from config import SUPABASE_JWT_SECRET, SUPABASE_URL

# Supabase кладёт "authenticated" в aud всем токенам залогиненных пользователей
# (анонимный aud — "anon", такие токены сюда доходить не должны).
AUDIENCE = "authenticated"

ASYMMETRIC_ALGORITHMS = ("ES256", "RS256")

_jwk_client = (
    jwt.PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    if SUPABASE_URL else None
)


def get_current_user_id(authorization: str | None = Header(default=None)) -> str:
    """FastAPI-зависимость: достаёт и проверяет Bearer-токен, возвращает user_id.

    401, если заголовка нет, он не Bearer, подпись не сошлась, токен истёк,
    алгоритм не поддержан или в токене нет sub. Так вместо "пользователь
    прислал вменяемый user_id" эндпоинт получает "Supabase Auth подтвердил,
    что это конкретный человек".
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Нужен заголовок Authorization: Bearer <access_token>",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Пустой токен")

    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Невалидный токен: {e}")

    try:
        if alg == "HS256":
            if not SUPABASE_JWT_SECRET:
                raise HTTPException(
                    status_code=500,
                    detail="SUPABASE_JWT_SECRET не задан на сервере, проверка токена невозможна",
                )
            payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience=AUDIENCE)
        elif alg in ASYMMETRIC_ALGORITHMS:
            if _jwk_client is None:
                raise HTTPException(
                    status_code=500,
                    detail="SUPABASE_URL не задан на сервере, проверка токена невозможна",
                )
            signing_key = _jwk_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(token, signing_key.key, algorithms=[alg], audience=AUDIENCE)
        else:
            raise HTTPException(status_code=401, detail=f"Неподдерживаемый алгоритм токена: {alg!r}")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Токен истёк, войдите заново")
    except jwt.PyJWKClientError as e:
        raise HTTPException(status_code=401, detail=f"Не удалось получить ключ проверки токена: {e}")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Невалидный токен: {e}")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="В токене нет sub (user_id)")
    return user_id
