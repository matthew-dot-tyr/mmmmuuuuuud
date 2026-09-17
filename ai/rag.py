"""Выбор карточек из базы знаний для вставки в промпт."""
import json
import random
from pathlib import Path

KB = json.loads((Path(__file__).parent / "knowledge_base.json").read_text(encoding="utf-8"))


def cards_for_scenario(character_level: int, k: int = 2) -> list[dict]:
    available = [c for c in KB if c["min_level"] <= character_level]
    return random.sample(available, min(k, len(available)))


def get_by_ids(ids: list[str]) -> list[dict]:
    return [c for c in KB if c["id"] in ids]


def search(text: str, k: int = 2) -> list[dict]:
    text = text.lower()
    scored = [(sum(tag in text for tag in c["tags"]), c) for c in KB]
    scored = [x for x in scored if x[0] > 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]


def format_cards(cards: list[dict]) -> str:
    return "\n\n".join(f"[{c['id']}] {c['title']}\n{c['content']}" for c in cards)
