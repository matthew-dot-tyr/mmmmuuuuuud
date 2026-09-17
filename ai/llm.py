"""
Обращение к Qwen через OpenRouter. Возвращает разобранный JSON.

Настройки скорости (см. .env.example):
- QWEN_MODEL — быстрая модель по умолчанию.
- reasoning.enabled=false — у ряда моделей Qwen3 по умолчанию включено скрытое
  "размышление" перед ответом: оно съедает токены из max_tokens, и при жёстком
  лимите итоговый JSON может не поместиться (ответ приходит пустым или обрезанным).
  Явно отключаем reasoning. Часть моделей требует reasoning обязательным и
  отклоняет запрос с ошибкой "Reasoning is mandatory..." — в этом случае
  автоматически повторяем запрос без этого параметра, но с увеличенным
  max_tokens, чтобы осталось место и на размышление, и на сам ответ.
- provider.sort=throughput — просим OpenRouter выбрать самого быстрого из
  доступных провайдеров этой модели, а не самого дешёвого.
- max_tokens ограничивает длину ответа: короче ответ — быстрее генерация.
"""
import json
import os
import re

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class AIError(Exception):
    """Модель недоступна или вернула непригодный ответ."""


_client = None


def _get_client():
    """
    trust_env=False отключает системный прокси Windows (часто SOCKS4, который
    httpx не поддерживает и который иначе ломает каждый запрос). Если для выхода
    в OpenRouter нужен прокси, укажите его явно в .env как OPENROUTER_PROXY.
    """
    global _client
    if _client is None:
        import httpx
        from openai import OpenAI
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise AIError("Не задан OPENROUTER_API_KEY в файле .env")
        proxy = os.environ.get("OPENROUTER_PROXY") or None
        http_client = httpx.Client(proxy=proxy, trust_env=False, timeout=30)
        _client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key, http_client=http_client)
    return _client


def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        preview = text[:200] + ("…" if len(text) > 200 else "")
        raise ValueError(f"В ответе нет JSON-объекта. Получено: {preview!r}")
    return json.loads(text[start:end + 1])


def _request(model: str, system: str, user: str, temperature: float,
             max_tokens: int, disable_reasoning: bool):
    extra_body = {"provider": {"sort": "throughput", "allow_fallbacks": True}}
    if disable_reasoning:
        extra_body["reasoning"] = {"enabled": False}
    resp = _get_client().chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        extra_body=extra_body,
    )
    return _extract_json(resp.choices[0].message.content)


def chat_json(system: str, user: str, temperature: float = 0.7,
              max_tokens: int = 400, retries: int = 1) -> dict:
    model = os.environ.get("QWEN_MODEL", "qwen/qwen3.8-flash-20260826")
    disable_reasoning = True
    attempt_max_tokens = max_tokens
    last_error = None
    for _ in range(retries + 1):
        try:
            return _request(model, system, user, temperature, attempt_max_tokens, disable_reasoning)
        except Exception as e:
            last_error = e
            # Не знаем заранее, эта ли модель требует reasoning обязательным (тогда она отклонит
            # reasoning.enabled=false с ошибкой 400) или просто съела весь лимит на скрытые
            # размышления, проигнорировав запрет. Поэтому на следующей попытке подстраховываемся
            # от обеих причин сразу: снимаем параметр и даём заметно больше места под ответ.
            disable_reasoning = False
            attempt_max_tokens = max(max_tokens * 3, 1200)
    raise AIError(f"Qwen не вернул корректный ответ: {last_error}")
