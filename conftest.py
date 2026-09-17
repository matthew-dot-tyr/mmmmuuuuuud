"""Общая настройка тестов.

Делает две вещи:
1. добавляет корень проекта в sys.path, чтобы работали импорты progress, db и т.д.;
2. подставляет фиктивные ключи и заглушку supabase, чтобы тесты шли
   без реальной базы и без .env.
"""

import os
import sys
import types

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")


class _NoDatabase:
    """Любое обращение к базе в тестах — ошибка: тесты подменяют функции db."""

    def __getattr__(self, name):
        raise RuntimeError(
            f"Тест попытался обратиться к базе (supabase.{name}). "
            "Подмени нужную функцию из db.py через monkeypatch."
        )


if "supabase" not in sys.modules:
    _fake = types.ModuleType("supabase")
    _fake.create_client = lambda url, key: _NoDatabase()
    sys.modules["supabase"] = _fake
