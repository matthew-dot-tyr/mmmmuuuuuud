"""Все переменные окружения в одном месте, с проверкой на старте.

Настройки самой модели (QWEN_MODEL, OPENROUTER_API_KEY, лимиты токенов,
прокси) читает AI-модуль в ai/llm.py — они сюда сознательно не дублируются,
чтобы не было двух источников правды.
"""

import os
import secrets

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Секрет для локальной проверки JWT, которые выпускает Supabase Auth (magic
# link). Project Settings -> API -> JWT Settings -> JWT Secret в дашборде.
# Без него auth.py не может проверить ни один токен — все запросы получат 401.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

# Домены фронтенда, через запятую. По умолчанию всё — на время разработки.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

# Прогресс игрока
XP_PER_LEVEL = int(os.getenv("XP_PER_LEVEL", "100"))
MAX_LEVEL = 3

# Ключ для подписи session, которую мы отдаём клиенту и принимаем обратно.
# Если не задан — генерируется случайный на время работы процесса: тогда после
# перезапуска сервера незакрытые переговоры придётся начать заново, и несколько
# воркеров не поймут подписи друг друга. Для деплоя задай его в окружении.
SESSION_SECRET = os.getenv("SESSION_SECRET") or secrets.token_hex(32)
SESSION_SECRET_IS_TEMPORARY = not os.getenv("SESSION_SECRET")


def require_supabase():
    """Вызывается там, где без Supabase работать нельзя."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "Не заданы SUPABASE_URL / SUPABASE_KEY. "
            "Скопируй .env.example в .env и заполни значения."
        )
    return SUPABASE_URL, SUPABASE_KEY
