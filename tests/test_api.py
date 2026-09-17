"""Интеграционные тесты эндпоинтов.

База, AI-движок и модель подменяются заглушками: тесты не ходят в Supabase
и не тратят токены OpenRouter. Запуск из корня проекта:  pytest -q
"""

import pytest
from fastapi.testclient import TestClient

import main
from progress import compute_level
from routers import users as users_router

client = TestClient(main.app)

OPTIONS = [{"option_id": "a", "text": "Предложу пересмотр через квартал"},
           {"option_id": "b", "text": "Соглашусь на их условия"},
           {"option_id": "c", "text": "Уйду из переговоров"}]

START_RESULT = {
    "session": {"difficulty": 1, "max_turns": 2, "turns_done": 0, "finished": False},
    "scenario_text": "Ты просишь повышение",
    "counterpart_opening": "Бюджета нет",
    "counterpart_role": "Руководитель",
    "counterpart_tone": "Уклончивый",
    "counterpart_goal": "Ничего не менять",
    "max_turns": 2,
    "options": OPTIONS,
}


@pytest.fixture
def fake_db(monkeypatch):
    """Пользователи в памяти вместо Supabase."""
    store = {"u1": {"id": "u1", "xp": 0, "level": 1}}
    claimed = set()

    def get_user(user_id):
        return store.get(user_id)

    def get_or_create_user(user_id):
        return store.setdefault(user_id, {"id": user_id, "xp": 0, "level": 1})

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

    monkeypatch.setattr(main, "get_or_create_user", get_or_create_user)
    monkeypatch.setattr(main, "add_xp", add_xp)
    monkeypatch.setattr(main, "claim_negotiation", claim_negotiation)
    monkeypatch.setattr(users_router, "get_user", get_user)
    monkeypatch.setattr(users_router, "get_or_create_user", get_or_create_user)
    return store


@pytest.fixture
def fake_ai(monkeypatch):
    """Подменяет движок: тесты задают, что вернёт start и очередной turn."""
    state = {"start": dict(START_RESULT), "turns": [], "calls": []}

    def start_negotiation(theme, difficulty, character_level):
        state["calls"].append(("start", theme, difficulty, character_level))
        result = dict(state["start"])
        result["session"] = {**result["session"], "difficulty": difficulty}
        return result

    def advance_turn(session, player_message):
        state["calls"].append(("turn", player_message))
        return dict(state["turns"].pop(0))

    monkeypatch.setattr(main, "start_negotiation", start_negotiation)
    monkeypatch.setattr(main, "advance_turn", advance_turn)
    return state


def _start(theme="work", difficulty=1, user_id="u1"):
    return client.post(
        "/negotiation/start",
        json={"user_id": user_id, "theme": theme, "difficulty": difficulty},
    )


def test_root():
    assert client.get("/").status_code == 200


# --- /user ---


def test_create_user(fake_db):
    res = client.post("/user", json={"user_id": "new-1"})
    assert res.status_code == 201
    body = res.json()
    assert (body["xp"], body["level"], body["xp_to_next_level"]) == (0, 1, 100)
    assert body["unlocked_difficulties"] == [1]


def test_read_user_progress(fake_db):
    fake_db["u1"].update(xp=150, level=2)
    body = client.get("/user/u1").json()
    assert body["xp_to_next_level"] == 50
    assert body["unlocked_difficulties"] == [1, 2]


def test_read_missing_user(fake_db):
    assert client.get("/user/нет-такого").status_code == 404


# --- /negotiation/start ---


def test_start_returns_scenario_and_token(fake_db, fake_ai):
    body = _start().json()
    assert body["scenario_text"] == "Ты просишь повышение"
    assert body["session_token"]
    assert "session" not in body           # сырую сессию клиенту не отдаём
    assert [o["option_id"] for o in body["options"]] == ["a", "b", "c"]


def test_start_translates_theme_slug(fake_db, fake_ai):
    _start(theme="money")
    assert fake_ai["calls"][0][1] == "Деньги и бизнес"


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
    assert fake_ai["calls"][0][3] == 3


# --- /negotiation/turn ---


def test_turn_continues_dialogue(fake_db, fake_ai):
    token = _start().json()["session_token"]
    fake_ai["turns"] = [{
        "continue": True,
        "counterpart_reply": "И что вы предлагаете?",
        "session": {"difficulty": 1, "turns_done": 1, "finished": False},
        "options": OPTIONS,
    }]
    body = client.post(
        "/negotiation/turn",
        json={"user_id": "u1", "session_token": token, "option_id": "a"},
    ).json()
    assert body["continue"] is True
    assert body["session_token"] != token
    # выбранный вариант дошёл до движка текстом, а не id
    assert fake_ai["calls"][-1] == ("turn", "Предложу пересмотр через квартал")


def test_turn_rejects_unknown_option(fake_db, fake_ai):
    token = _start().json()["session_token"]
    res = client.post(
        "/negotiation/turn",
        json={"user_id": "u1", "session_token": token, "option_id": "zzz"},
    )
    assert res.status_code == 400
    assert "zzz" in res.json()["detail"]


def test_turn_requires_answer(fake_db, fake_ai):
    token = _start().json()["session_token"]
    res = client.post("/negotiation/turn", json={"user_id": "u1", "session_token": token})
    assert res.status_code == 422


def test_turn_awards_xp_on_success(fake_db, fake_ai):
    token = _start().json()["session_token"]
    fake_ai["turns"] = [{
        "continue": False,
        "counterpart_reply": "Хорошо, договорились",
        "outcome": "success",
        "score": 9,
        "feedback_text": "Держал позицию",
    }]
    body = client.post(
        "/negotiation/turn",
        json={"user_id": "u1", "session_token": token, "option_id": "a"},
    ).json()
    assert body["xp_gained"] == 45          # 9 * множитель сложности 1
    assert body["xp"] == 45
    assert body["level_up"] is False
    assert "session_token" not in body      # переговоры закрыты


def test_turn_awards_fixed_xp_on_failure(fake_db, fake_ai):
    token = _start().json()["session_token"]
    fake_ai["turns"] = [{
        "continue": False,
        "counterpart_reply": "Разговор окончен",
        "outcome": "failure",
        "score": None,
        "feedback_text": "Сдался сразу",
    }]
    body = client.post(
        "/negotiation/turn",
        json={"user_id": "u1", "session_token": token, "option_id": "b"},
    ).json()
    assert body["xp_gained"] == 5


def test_xp_accumulates_across_negotiations(fake_db, fake_ai):
    """Прогресс копится между переговорами и поднимает уровень."""
    final = {
        "continue": False,
        "counterpart_reply": "ок",
        "outcome": "success",
        "score": 9,
        "feedback_text": "хорошо",
    }
    seen = []
    for _ in range(3):
        token = _start().json()["session_token"]
        fake_ai["turns"] = [dict(final)]
        seen.append(client.post(
            "/negotiation/turn",
            json={"user_id": "u1", "session_token": token, "option_id": "a"},
        ).json())

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
        "feedback_text": "отлично",
    }
    fake_ai["turns"] = [dict(final), dict(final)]
    body = {"user_id": "u1", "session_token": token, "option_id": "a"}

    assert client.post("/negotiation/turn", json=body).status_code == 200
    again = client.post("/negotiation/turn", json=body)
    assert again.status_code == 409
    assert fake_db["u1"]["xp"] == 50        # XP начислен один раз


def test_turn_rejects_foreign_token(fake_db, fake_ai):
    token = _start(user_id="u1").json()["session_token"]
    res = client.post(
        "/negotiation/turn",
        json={"user_id": "другой", "session_token": token, "option_id": "a"},
    )
    assert res.status_code == 403


def test_turn_rejects_tampered_token(fake_db, fake_ai):
    token = _start().json()["session_token"]
    data, sig = token.split(".")
    res = client.post(
        "/negotiation/turn",
        json={"user_id": "u1", "session_token": f"{data}x.{sig}", "option_id": "a"},
    )
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
    res = client.post(
        "/negotiation/turn",
        json={"user_id": "u1", "session_token": token, "message": "Давайте обсудим сроки"},
    )
    assert res.status_code == 200
    assert fake_ai["calls"][-1] == ("turn", "Давайте обсудим сроки")


def test_ai_unavailable_returns_503(fake_db, fake_ai, monkeypatch):
    def boom(*args, **kwargs):
        raise main.AIError("Qwen не ответил")

    monkeypatch.setattr(main, "start_negotiation", boom)
    assert _start().status_code == 503


def test_contract_error_returns_400(fake_db, fake_ai, monkeypatch):
    def boom(*args, **kwargs):
        raise main.ContractError("плохие входные данные")

    monkeypatch.setattr(main, "start_negotiation", boom)
    assert _start().status_code == 400
