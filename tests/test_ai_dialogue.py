"""Закрепляет два инварианта AI-движка тестом (см. инструкцию по кастомным
ситуациям, задача бэкендера 1, шаг 2):

1. Судья на ходу диалога видит только СГЕНЕРИРОВАННЫЙ сценарий
   (session.scenario_text / counterpart_role/tone/goal), а не исходный текст,
   который ввёл пользователь в mode="custom". Если это разъедется при
   следующей правке промпта, тест должен упасть, а не автор случайно заметить
   на демо, что модель оценивает качество формулировки пользователя.
2. session.theme is None в кастомном режиме не роняет ничего ниже по потоку
   (сериализацию Session, advance_turn, prompts.turn_user).
"""

import ai
from ai import dialogue, llm


BASE_START_RESPONSE = {
    "is_negotiation": True,
    "scenario_text": "Сосед по площадке жалуется на шум по вечерам.",
    "counterpart_opening": "«Ваша музыка мешает мне с восьми вечера», — говорит сосед.",
    "counterpart_role": "Сосед Пётр, 60 лет",
    "counterpart_tone": "Раздражён, но готов услышать доводы",
    "counterpart_goal": "Добиться полной тишины после восьми",
    "principles_used": ["harvard_criteria"],
    "options": [{"text": "Предложить компромисс по времени"},
                {"text": "Извиниться и пообещать тишину"},
                {"text": "Настоять на своём праве шуметь до десяти"}],
}


def test_custom_situation_not_leaked_into_turn_prompt(monkeypatch):
    marker = "УНИКАЛЬНЫЙ_МАРКЕР_ИЗ_ТЕКСТА_ПОЛЬЗОВАТЕЛЯ"
    custom_situation = f"Хочу договориться с соседом о шуме. {marker} Помогите мне выиграть."

    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: dict(BASE_START_RESPONSE))

    start, session = ai.start_negotiation(
        "custom", difficulty=1, character_level=1, custom_situation=custom_situation,
    )

    assert session.theme is None
    assert marker not in session.scenario_text
    assert marker not in session.counterpart_goal

    prompt = ai.prompts.turn_user(session, "ответ игрока", materials="", force_end=False)
    assert marker not in prompt
    assert custom_situation not in prompt


def test_theme_none_does_not_break_advance_turn(monkeypatch):
    """session.theme is None (mode=custom) не мешает продолжить диалог обычным ходом."""
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: dict(BASE_START_RESPONSE))
    start, session = ai.start_negotiation(
        "custom", difficulty=1, character_level=1,
        custom_situation="Хочу договориться с соседом о шуме, он включает музыку по вечерам",
    )
    assert session.theme is None

    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {
        "ends": False,
        "counterpart_reply": "Хорошо, а что вы предлагаете взамен?",
        "options": [{"text": "a"}, {"text": "b"}, {"text": "c"}],
    })
    result, new_session = ai.advance_turn(session, "Давайте договоримся на девять вечера")
    assert result.ends is False
    assert new_session.theme is None
    # Сериализация session -> dict -> обратно тоже не должна спотыкаться на theme=None.
    round_tripped = ai.Session.from_dict(new_session.to_dict())
    assert round_tripped.theme is None
