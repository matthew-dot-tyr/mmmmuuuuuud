"""Интеграционные тесты эндпоинтов.

База, AI-движок и модель подменяются заглушками: тесты не ходят в Supabase
и не тратят токены OpenRouter. Аутентификация (Supabase Auth JWT) тоже
подменяется через dependency_overrides — реальную проверку токена (auth.py)
покрывают test_auth.py и test_negotiation_requires_real_bearer_token ниже.
Запуск из корня проекта:  pytest -q
"""

import contextlib

import pytest
from fastapi.testclient import TestClient

import main
from auth import get_current_user_id
from progress import compute_level
from routers import users as users_router

client = TestClient(main.app)

OPTIONS = [{"option_id": "a", "text": "Предложу пересмотр через квартал"},
           {"option_id": "b", "text": "Соглашусь на их условия"},
           {"option_id": "c", "text": "Уйду из переговоров"}]

START_RESULT = {
    "session": {"difficulty": 1, "turns_done": 0, "finished": False},
    "scenario_text": "Ты просишь повышение",
    "counterpart_opening": "Бюджета нет",
    "counterpart_role": "Руководитель",
    "counterpart_tone": "Уклончивый",
    "counterpart_goal": "Ничего не менять",
    "options": OPTIONS,
}

# Валидный (>= 30 символов, без ссылок/мусора) текст для mode=custom.
VALID_CUSTOM_TEXT = "Хочу договориться с соседом, чтобы он не шумел после десяти вечера"

# --- имитация авторизованного пользователя ---
# user_id клиент больше не присылает: он приходит из проверенного JWT
# (auth.get_current_user_id). В тестах эту зависимость подменяем, чтобы не
# генерировать настоящие токены на каждый чих — кто "текущий пользователь"
# в конкретном запросе, управляется значением CURRENT_USER.

CURRENT_USER = {"id": "u1"}


def _fake_current_user_id():
    return CURRENT_USER["id"]


@pytest.fixture(autouse=True)
def _auth_override():
    main.app.dependency_overrides[get_current_user_id] = _fake_current_user_id
    CURRENT_USER["id"] = "u1"
    yield
    main.app.dependency_overrides.pop(get_current_user_id, None)


@contextlib.contextmanager
def as_user(user_id):
    """Временно подменяет "текущего" пользователя на другого — для тестов
    межпользовательской изоляции (чужой токен = чужой session_token)."""
    previous = CURRENT_USER["id"]
    CURRENT_USER["id"] = user_id
    try:
        yield
    finally:
        CURRENT_USER["id"] = previous


@pytest.fixture
def fake_db(monkeypatch):
    """Пользователи в памяти вместо Supabase, аналитика — тоже в памяти."""
    store = {"u1": {"id": "u1", "xp": 0, "level": 1, "streak_count": 0, "last_practiced_date": None}}
    claimed = set()
    negotiations_logged = []
    refusals_logged = []
    ai_errors_logged = []
    attempts_logged = []
    attempts_by_user = {}

    def get_user(user_id):
        return store.get(user_id)

    def get_or_create_user(user_id):
        return store.setdefault(
            user_id, {"id": user_id, "xp": 0, "level": 1, "streak_count": 0, "last_practiced_date": None},
        )

    def add_xp(user_id, gained):
        user = get_or_create_user(user_id)
        user["xp"] += gained
        user["level"] = compute_level(user["xp"])
        return {"xp": user["xp"], "level": user["level"]}

    def claim_negotiation(negotiation_id, user_id):
        if negotiation_id in claimed:
            return False
        claimed.add(negotiation_id)
        return True

    def log_negotiation(negotiation_id, user_id, mode, theme, custom_situation,
                        difficulty, character_level):
        negotiations_logged.append({
            "negotiation_id": negotiation_id, "user_id": user_id, "mode": mode,
            "theme": theme, "custom_situation": custom_situation,
            "difficulty": difficulty, "character_level": character_level,
        })

    def allow_generation(user_id, mode, client_ip):
        return True

    def log_refusal(user_id, req, reason, raw="", client_ip=None):
        refusals_logged.append({"user_id": user_id, "reason": reason, "raw": raw, "client_ip": client_ip})

    def log_ai_error(user_id, req, error, client_ip=None):
        ai_errors_logged.append({"user_id": user_id, "error": error, "client_ip": client_ip})

    def log_attempt(user_id, theme, level, success, score):
        attempt = {"id": str(len(attempts_logged) + 1), "user_id": user_id, "theme": theme,
                   "level": level, "success": success, "score": score, "created_at": "2026-09-27T00:00:00+00:00"}
        attempts_logged.append(attempt)
        attempts_by_user.setdefault(user_id, []).insert(0, attempt)

    def get_attempts(user_id, limit=20):
        return attempts_by_user.get(user_id, [])[:limit]

    def update_user_streak(user_id, streak_count, last_practiced_date):
        user = get_or_create_user(user_id)
        user["streak_count"] = streak_count
        user["last_practiced_date"] = last_practiced_date.isoformat()

    monkeypatch.setattr(main, "get_or_create_user", get_or_create_user)
    monkeypatch.setattr(main, "get_user", get_user)
    monkeypatch.setattr(main, "add_xp", add_xp)
    monkeypatch.setattr(main, "claim_negotiation", claim_negotiation)
    monkeypatch.setattr(main, "log_negotiation", log_negotiation)
    monkeypatch.setattr(main, "allow_generation", allow_generation)
    monkeypatch.setattr(main, "log_refusal", log_refusal)
    monkeypatch.setattr(main, "log_ai_error", log_ai_error)
    monkeypatch.setattr(main, "log_attempt", log_attempt)
    monkeypatch.setattr(main, "update_user_streak", update_user_streak)
    monkeypatch.setattr(users_router, "get_user", get_user)
    monkeypatch.setattr(users_router, "get_or_create_user", get_or_create_user)
    monkeypatch.setattr(users_router, "get_attempts", get_attempts)
    store["_negotiations_logged"] = negotiations_logged
    store["_refusals_logged"] = refusals_logged
    store["_ai_errors_logged"] = ai_errors_logged
    store["_attempts_logged"] = attempts_logged
    return store


@pytest.fixture
def fake_ai(monkeypatch):
    """Подменяет движок: тесты задают, что вернёт start и очередной turn."""
    state = {"start": dict(START_RESULT), "turns": [], "calls": []}

    def start_negotiation(mode, difficulty, character_level, theme=None, custom_situation=None):
        state["calls"].append(("start", mode, theme, custom_situation, difficulty, character_level))
        result = dict(state["start"])
        if "session" in result:
            # Реальный Session.to_dict() всегда содержит "theme" (человеческое
            # название или None для custom) — отражаем это и в заглушке,
            # иначе log_attempt в main.py увидит session.get("theme") == None
            # даже для mode=theme, что не соответствует реальному поведению.
            result["session"] = {**result["session"], "difficulty": difficulty, "theme": theme}
        return result

    def advance_turn(session, player_message):
        state["calls"].append(("turn", player_message))
        return dict(state["turns"].pop(0))

    monkeypatch.setattr(main, "start_negotiation", start_negotiation)
    monkeypatch.setattr(main, "advance_turn", advance_turn)
    return state


def _start(theme="work", difficulty=1, mode=None, custom_situation=None):
    body = {"difficulty": difficulty}
    if mode is not None:
        body["mode"] = mode
    if mode == "custom":
        body["custom_situation"] = custom_situation
    else:
        body["theme"] = theme
    return client.post("/negotiation/start", json=body)


def _turn(session_token, **payload):
    return client.post("/negotiation/turn", json={"session_token": session_token, **payload})


def test_root():
    assert client.get("/").status_code == 200


# --- /user ---


def test_create_user(fake_db):
    res = client.post("/user", json={})
    assert res.status_code == 201
    body = res.json()
    assert body["user_id"] == "u1"          # взят из (подменённого) токена
    assert (body["xp"], body["level"], body["xp_to_next_level"]) == (0, 1, 100)
    assert body["unlocked_difficulties"] == [1]


def test_read_current_user_progress(fake_db):
    fake_db["u1"].update(xp=150, level=2)
    body = client.get("/user/me").json()
    assert body["xp_to_next_level"] == 50
    assert body["unlocked_difficulties"] == [1, 2]


def test_read_current_user_creates_nothing_if_missing(fake_db):
    with as_user("нет-такого"):
        assert client.get("/user/me").status_code == 404


# --- /negotiation/start: режим theme (старое поведение) ---


def test_start_returns_scenario_and_token(fake_db, fake_ai):
    body = _start().json()
    assert body["scenario_text"] == "Ты просишь повышение"
    assert body["session_token"]
    assert "session" not in body           # сырую сессию клиенту не отдаём
    assert "max_turns" not in body         # поля больше нет в контракте
    assert "user_id" not in body           # и user_id тоже не эхо, а не поле ответа
    assert [o["option_id"] for o in body["options"]] == ["a", "b", "c"]


def test_start_default_mode_is_theme(fake_db, fake_ai):
    """Старые клиенты не шлют mode вовсе — должны продолжать работать."""
    res = _start(mode=None)
    assert res.status_code == 200
    assert fake_ai["calls"][0][1] == "theme"


def test_start_translates_theme_slug(fake_db, fake_ai):
    _start(theme="money")
    assert fake_ai["calls"][0][2] == "Деньги и бизнес"


def test_start_rejects_unknown_theme(fake_db, fake_ai):
    assert _start(theme="готовка").status_code == 422


def test_start_blocks_locked_difficulty(fake_db, fake_ai):
    res = _start(difficulty=3)
    assert res.status_code == 403
    assert fake_ai["calls"] == []          # к модели не ходили


def test_start_allows_difficulty_at_player_level(fake_db, fake_ai):
    fake_db["u1"].update(xp=100, level=2)
    assert _start(difficulty=2).status_code == 200


def test_start_passes_player_level_to_engine(fake_db, fake_ai):
    fake_db["u1"].update(xp=200, level=3)
    _start(difficulty=3)
    assert fake_ai["calls"][0][5] == 3


def test_start_logs_negotiation(fake_db, fake_ai):
    _start(theme="work")
    logged = fake_db["_negotiations_logged"]
    assert len(logged) == 1
    assert logged[0]["user_id"] == "u1"    # из токена, не из тела запроса
    assert logged[0]["mode"] == "theme"
    assert logged[0]["theme"] == "work"    # слаг, не человеческое название
    assert logged[0]["custom_situation"] is None


def test_start_uses_user_id_from_token_not_body(fake_db, fake_ai):
    """Тело запроса больше не содержит user_id вообще — попытка прислать его
    (как раньше) ни на что не влияет, реальный пользователь — из токена."""
    res = client.post("/negotiation/start", json={
        "user_id": "чужой-id-в-теле-запроса", "mode": "theme", "theme": "work", "difficulty": 1,
    })
    assert res.status_code == 200
    assert fake_db["_negotiations_logged"][0]["user_id"] == "u1"


# --- /negotiation/start: mode=theme и custom взаимоисключающи (422) ---


def test_start_theme_mode_with_custom_situation_is_422(fake_db, fake_ai):
    res = client.post("/negotiation/start", json={
        "mode": "theme", "theme": "work",
        "custom_situation": VALID_CUSTOM_TEXT, "difficulty": 1,
    })
    assert res.status_code == 422


def test_start_custom_mode_without_text_is_422(fake_db, fake_ai):
    res = client.post("/negotiation/start", json={"mode": "custom", "difficulty": 1})
    assert res.status_code == 422


def test_start_custom_mode_with_theme_is_422(fake_db, fake_ai):
    res = client.post("/negotiation/start", json={
        "mode": "custom", "theme": "work",
        "custom_situation": VALID_CUSTOM_TEXT, "difficulty": 1,
    })
    assert res.status_code == 422


# --- /negotiation/start: mode=custom ---


def test_start_custom_success(fake_db, fake_ai):
    res = _start(mode="custom", custom_situation=VALID_CUSTOM_TEXT)
    assert res.status_code == 200
    body = res.json()
    assert "rejected" not in body
    assert fake_ai["calls"][0][1] == "custom"
    assert fake_ai["calls"][0][3] == VALID_CUSTOM_TEXT
    assert fake_ai["calls"][0][2] is None   # theme не передан


def test_start_custom_logs_situation_not_theme(fake_db, fake_ai):
    _start(mode="custom", custom_situation=VALID_CUSTOM_TEXT)
    logged = fake_db["_negotiations_logged"][0]
    assert logged["mode"] == "custom"
    assert logged["theme"] is None
    assert logged["custom_situation"] == VALID_CUSTOM_TEXT


def test_start_custom_rejects_short_text_locally(fake_db, fake_ai):
    """Локальная валидация — движок вообще не вызывается (бесплатно)."""
    res = _start(mode="custom", custom_situation="коротко")
    assert res.status_code == 200
    body = res.json()
    assert body == {"rejected": True, "reason": "too_short", "message": body["message"]}
    assert fake_ai["calls"] == []
    assert fake_db["_refusals_logged"][0]["reason"].value == "too_short"
    assert fake_db["_refusals_logged"][0]["user_id"] == "u1"


def test_start_custom_rejects_link_locally(fake_db, fake_ai):
    res = _start(mode="custom", custom_situation=VALID_CUSTOM_TEXT + " https://example.com")
    assert res.json()["reason"] == "contains_link"
    assert fake_ai["calls"] == []


def test_start_custom_model_rejection_is_not_an_exception(fake_db, fake_ai):
    """Отказ модели возвращается значением (HTTP 200), а не бросает исключение."""
    fake_ai["start"] = {"rejected": True, "reason": "not_a_negotiation"}
    res = _start(mode="custom", custom_situation=VALID_CUSTOM_TEXT)
    assert res.status_code == 200
    body = res.json()
    assert body["rejected"] is True
    assert body["reason"] == "not_a_negotiation"
    assert body["message"]
    assert fake_db["_refusals_logged"][0]["reason"].value == "not_a_negotiation"


def test_start_rate_limited(fake_db, fake_ai, monkeypatch):
    monkeypatch.setattr(main, "allow_generation", lambda *a, **k: False)
    res = _start(mode="custom", custom_situation=VALID_CUSTOM_TEXT)
    assert res.status_code == 200
    body = res.json()
    assert body == {"rejected": True, "reason": "rate_limited", "message": body["message"]}
    assert fake_ai["calls"] == []


def test_ai_unavailable_returns_503_and_logs(fake_db, fake_ai, monkeypatch):
    def boom(*args, **kwargs):
        raise main.AIError("Qwen не ответил")

    monkeypatch.setattr(main, "start_negotiation", boom)
    res = _start()
    assert res.status_code == 503
    assert fake_db["_ai_errors_logged"][0]["error"] == "Qwen не ответил"
    assert fake_db["_ai_errors_logged"][0]["user_id"] == "u1"


def test_contract_error_returns_400(fake_db, fake_ai, monkeypatch):
    def boom(*args, **kwargs):
        raise main.ContractError("плохие входные данные")

    monkeypatch.setattr(main, "start_negotiation", boom)
    assert _start().status_code == 400


# --- аутентификация: без валидного токена ничего не работает ---


def test_start_requires_auth(fake_db, fake_ai):
    main.app.dependency_overrides.pop(get_current_user_id, None)
    try:
        res = client.post("/negotiation/start", json={"mode": "theme", "theme": "work", "difficulty": 1})
        assert res.status_code == 401
    finally:
        main.app.dependency_overrides[get_current_user_id] = _fake_current_user_id


def test_user_endpoints_require_auth(fake_db):
    main.app.dependency_overrides.pop(get_current_user_id, None)
    try:
        assert client.post("/user", json={}).status_code == 401
        assert client.get("/user/me").status_code == 401
    finally:
        main.app.dependency_overrides[get_current_user_id] = _fake_current_user_id


def test_negotiation_requires_real_bearer_token(fake_db, fake_ai):
    """Сквозная проверка настоящего auth.py (не через override): без токена —
    401, с корректно подписанным Supabase JWT — обычный успешный ответ."""
    import time

    import jwt

    main.app.dependency_overrides.pop(get_current_user_id, None)
    try:
        no_auth = client.post("/negotiation/start", json={"mode": "theme", "theme": "work", "difficulty": 1})
        assert no_auth.status_code == 401

        token = jwt.encode(
            {"sub": "u1", "aud": "authenticated", "exp": time.time() + 3600},
            "test-jwt-secret-at-least-32-bytes-long", algorithm="HS256",
        )
        authed = client.post(
            "/negotiation/start",
            json={"mode": "theme", "theme": "work", "difficulty": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert authed.status_code == 200
    finally:
        main.app.dependency_overrides[get_current_user_id] = _fake_current_user_id


# --- /negotiation/turn ---


def test_turn_continues_dialogue(fake_db, fake_ai):
    token = _start().json()["session_token"]
    fake_ai["turns"] = [{
        "continue": True,
        "counterpart_reply": "И что вы предлагаете?",
        "session": {"difficulty": 1, "turns_done": 1, "finished": False},
        "options": OPTIONS,
    }]
    body = _turn(token, option_id="a").json()
    assert body["continue"] is True
    assert body["session_token"] != token
    # выбранный вариант дошёл до движка текстом, а не id
    assert fake_ai["calls"][-1] == ("turn", "Предложу пересмотр через квартал")


def test_turn_rejects_unknown_option(fake_db, fake_ai):
    token = _start().json()["session_token"]
    res = _turn(token, option_id="zzz")
    assert res.status_code == 400
    assert "zzz" in res.json()["detail"]


def test_turn_requires_answer(fake_db, fake_ai):
    token = _start().json()["session_token"]
    res = client.post("/negotiation/turn", json={"session_token": token})
    assert res.status_code == 422


def test_turn_awards_xp_on_success_with_structured_feedback(fake_db, fake_ai):
    token = _start().json()["session_token"]
    fake_ai["turns"] = [{
        "continue": False,
        "counterpart_reply": "Хорошо, договорились",
        "outcome": "success",
        "score": 9,
        "feedback": {
            "broke_quote": None, "broke_reason": None,
            "what_worked": "Держал позицию", "alternative_phrasing": None,
            "tip": "Продолжайте в том же духе",
        },
    }]
    body = _turn(token, option_id="a").json()
    assert body["xp_gained"] == 45          # 9 * множитель сложности 1
    assert body["xp"] == 45
    assert body["level_up"] is False
    assert "session_token" not in body      # переговоры закрыты
    assert isinstance(body["feedback"], dict)
    assert body["feedback"]["tip"] == "Продолжайте в том же духе"


def test_turn_feedback_can_degrade_to_string(fake_db, fake_ai):
    """Клиент обязан проверять тип: движок иногда деградирует feedback до строки."""
    token = _start().json()["session_token"]
    fake_ai["turns"] = [{
        "continue": False,
        "counterpart_reply": "Разговор окончен",
        "outcome": "failure",
        "score": None,
        "feedback": "Сдался сразу — не удалось собрать структурный разбор",
    }]
    body = _turn(token, option_id="b").json()
    assert isinstance(body["feedback"], str)
    assert body["xp_gained"] == 5


# --- лог попыток и стрик ---


def _finish(theme="work", outcome="success", score=9, difficulty=1):
    """Стартует и сразу завершает переговоры с заданным исходом."""
    token = _start(theme=theme, difficulty=difficulty).json()["session_token"]
    return _turn(token, option_id="a")


def test_finishing_negotiation_logs_attempt(fake_db, fake_ai):
    fake_ai["turns"] = [{
        "continue": False, "counterpart_reply": "ок", "outcome": "success", "score": 7,
        "feedback": {"broke_quote": None, "broke_reason": None, "what_worked": None,
                     "alternative_phrasing": None, "tip": "совет"},
    }]
    _finish(theme="work")

    logged = fake_db["_attempts_logged"]
    assert len(logged) == 1
    assert logged[0]["user_id"] == "u1"
    assert logged[0]["theme"] == "work"     # тема из СЕССИИ (слаг), не из тела запроса
    assert logged[0]["level"] == 1          # сложность сценария, session["difficulty"]
    assert logged[0]["success"] is True
    assert logged[0]["score"] == 7


def test_failed_attempt_is_logged_too(fake_db, fake_ai):
    fake_ai["turns"] = [{
        "continue": False, "counterpart_reply": "разрыв", "outcome": "failure", "score": None,
        "feedback": {"broke_quote": None, "broke_reason": None, "what_worked": None,
                     "alternative_phrasing": None, "tip": "совет"},
    }]
    _finish()
    assert fake_db["_attempts_logged"][0]["success"] is False
    assert fake_db["_attempts_logged"][0]["score"] is None


def test_custom_mode_attempt_has_no_theme(fake_db, fake_ai):
    token = _start(mode="custom", custom_situation=VALID_CUSTOM_TEXT).json()["session_token"]
    fake_ai["turns"] = [{
        "continue": False, "counterpart_reply": "ок", "outcome": "success", "score": 5,
        "feedback": {"broke_quote": None, "broke_reason": None, "what_worked": None,
                     "alternative_phrasing": None, "tip": "совет"},
    }]
    _turn(token, option_id="a")
    assert fake_db["_attempts_logged"][0]["theme"] is None


def test_attempts_endpoint_returns_logged_attempts(fake_db, fake_ai):
    fake_ai["turns"] = [{
        "continue": False, "counterpart_reply": "ок", "outcome": "success", "score": 6,
        "feedback": {"broke_quote": None, "broke_reason": None, "what_worked": None,
                     "alternative_phrasing": None, "tip": "совет"},
    }]
    _finish(theme="money")

    res = client.get("/attempts")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["theme"] == "money"
    assert body[0]["success"] is True
    assert body[0]["score"] == 6


def test_attempts_endpoint_requires_auth(fake_db):
    main.app.dependency_overrides.pop(get_current_user_id, None)
    try:
        assert client.get("/attempts").status_code == 401
        assert client.get("/streak").status_code == 401
    finally:
        main.app.dependency_overrides[get_current_user_id] = _fake_current_user_id


def test_streak_starts_at_one_on_first_ever_attempt(fake_db, fake_ai):
    """last_practiced_date ещё нет -> первая попытка сразу даёт стрик 1,
    независимо от того, какая сегодня дата (детерминированно без мока даты)."""
    fake_ai["turns"] = [{
        "continue": False, "counterpart_reply": "ок", "outcome": "success", "score": 5,
        "feedback": {"broke_quote": None, "broke_reason": None, "what_worked": None,
                     "alternative_phrasing": None, "tip": "совет"},
    }]
    _finish()

    res = client.get("/streak")
    assert res.status_code == 200
    body = res.json()
    assert body["streak_count"] == 1
    assert body["last_practiced_date"] == fake_db["u1"]["last_practiced_date"]


def test_streak_does_not_increment_twice_same_day(fake_db, fake_ai, monkeypatch):
    """Две попытки в один день не должны давать стрик 2."""
    import datetime as dt

    fixed_today = dt.date(2026, 9, 27)

    class _FixedDate(dt.date):
        @classmethod
        def today(cls):
            return fixed_today

    monkeypatch.setattr(main, "date", _FixedDate)
    monkeypatch.setattr("progress.date", _FixedDate)

    final = {
        "continue": False, "counterpart_reply": "ок", "outcome": "success", "score": 5,
        "feedback": {"broke_quote": None, "broke_reason": None, "what_worked": None,
                     "alternative_phrasing": None, "tip": "совет"},
    }
    fake_ai["turns"] = [dict(final)]
    _finish()
    fake_ai["turns"] = [dict(final)]
    _finish()

    assert client.get("/streak").json()["streak_count"] == 1


def test_streak_increments_on_consecutive_days(fake_db, fake_ai, monkeypatch):
    import datetime as dt

    day1 = dt.date(2026, 9, 27)
    day2 = day1 + dt.timedelta(days=1)

    class _Day1(dt.date):
        @classmethod
        def today(cls):
            return day1

    class _Day2(dt.date):
        @classmethod
        def today(cls):
            return day2

    final = {
        "continue": False, "counterpart_reply": "ок", "outcome": "success", "score": 5,
        "feedback": {"broke_quote": None, "broke_reason": None, "what_worked": None,
                     "alternative_phrasing": None, "tip": "совет"},
    }

    monkeypatch.setattr(main, "date", _Day1)
    monkeypatch.setattr("progress.date", _Day1)
    fake_ai["turns"] = [dict(final)]
    _finish()
    assert client.get("/streak").json()["streak_count"] == 1

    monkeypatch.setattr(main, "date", _Day2)
    monkeypatch.setattr("progress.date", _Day2)
    fake_ai["turns"] = [dict(final)]
    _finish()
    assert client.get("/streak").json()["streak_count"] == 2


def test_streak_resets_after_missed_day(fake_db, fake_ai, monkeypatch):
    import datetime as dt

    day1 = dt.date(2026, 9, 27)
    day3 = day1 + dt.timedelta(days=2)   # день 2 пропущен

    class _Day1(dt.date):
        @classmethod
        def today(cls):
            return day1

    class _Day3(dt.date):
        @classmethod
        def today(cls):
            return day3

    final = {
        "continue": False, "counterpart_reply": "ок", "outcome": "success", "score": 5,
        "feedback": {"broke_quote": None, "broke_reason": None, "what_worked": None,
                     "alternative_phrasing": None, "tip": "совет"},
    }

    monkeypatch.setattr(main, "date", _Day1)
    monkeypatch.setattr("progress.date", _Day1)
    fake_ai["turns"] = [dict(final)]
    _finish()
    assert client.get("/streak").json()["streak_count"] == 1

    monkeypatch.setattr(main, "date", _Day3)
    monkeypatch.setattr("progress.date", _Day3)
    fake_ai["turns"] = [dict(final)]
    _finish()
    assert client.get("/streak").json()["streak_count"] == 1   # сброс, не 2


def test_xp_accumulates_across_negotiations(fake_db, fake_ai):
    """Прогресс копится между переговорами и поднимает уровень."""
    final = {
        "continue": False,
        "counterpart_reply": "ок",
        "outcome": "success",
        "score": 9,
        "feedback": {"broke_quote": None, "broke_reason": None, "what_worked": None,
                     "alternative_phrasing": None, "tip": "хорошо"},
    }
    seen = []
    for _ in range(3):
        token = _start().json()["session_token"]
        fake_ai["turns"] = [dict(final)]
        seen.append(_turn(token, option_id="a").json())

    assert [r["xp"] for r in seen] == [45, 90, 135]
    assert seen[-1]["level"] == 2
    assert seen[-1]["level_up"] is True


def test_finished_negotiation_cannot_be_replayed(fake_db, fake_ai):
    """Один и тот же выигрышный ход нельзя сдать дважды."""
    token = _start().json()["session_token"]
    final = {
        "continue": False,
        "counterpart_reply": "ок",
        "outcome": "success",
        "score": 10,
        "feedback": {"broke_quote": None, "broke_reason": None, "what_worked": None,
                     "alternative_phrasing": None, "tip": "отлично"},
    }
    fake_ai["turns"] = [dict(final), dict(final)]

    assert _turn(token, option_id="a").status_code == 200
    again = _turn(token, option_id="a")
    assert again.status_code == 409
    assert fake_db["u1"]["xp"] == 50        # XP начислен один раз


def test_turn_rejects_foreign_token(fake_db, fake_ai):
    token = _start().json()["session_token"]          # переговоры начал u1
    with as_user("другой"):                            # а ход шлёт другой токен
        res = _turn(token, option_id="a")
    assert res.status_code == 403


def test_turn_rejects_tampered_token(fake_db, fake_ai):
    token = _start().json()["session_token"]
    data, sig = token.split(".")
    res = _turn(f"{data}x.{sig}", option_id="a")
    assert res.status_code == 400


def test_free_text_on_max_difficulty(fake_db, fake_ai):
    fake_db["u1"].update(xp=200, level=3)
    start = dict(START_RESULT)
    start.pop("options")                    # на сложности 3 вариантов нет
    fake_ai["start"] = start

    token = _start(difficulty=3).json()["session_token"]
    fake_ai["turns"] = [{
        "continue": True,
        "counterpart_reply": "Слушаю",
        "session": {"difficulty": 3, "turns_done": 1, "finished": False},
    }]
    res = _turn(token, message="Давайте обсудим сроки")
    assert res.status_code == 200
    assert fake_ai["calls"][-1] == ("turn", "Давайте обсудим сроки")
