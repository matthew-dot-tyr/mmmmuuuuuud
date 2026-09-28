"""
Консольная версия тренажёра: играем в переговоры без фронтенда.

Ходит в запущенный сервер по HTTP, то есть проверяет всю цепочку целиком —
API, движок диалога, модель, Supabase, начисление XP и блокировку сложностей.

Запуск (в другом окне терминала, пока работает uvicorn):
    python play.py

Адрес сервера при необходимости:
    python play.py http://127.0.0.1:8000

Аутентификация — Supabase Auth (magic link), не user_id. У этого скрипта нет
браузера, чтобы пройти вход по ссылке из письма самому, поэтому он просит
вставить уже готовый access_token один раз, а дальше хранит его в .play_token
(не в гите) и переиспользует, пока токен не истечёт. Получить токен можно на
странице /play (там есть вход по magic link) — после входа он лежит в
localStorage браузера под ключом "arena_access_token", либо через
supabase.auth.signInWithOtp(...) / signInWithOtp + verifyOtp в консоли
браузера, если делаете это руками.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
TOKEN_FILE = Path(".play_token")
TIMEOUT = 120  # модель может думать долго
ACCESS_TOKEN = None  # заполняется в main() -> ensure_access_token()

THEMES = [
    ("work", "Работа и карьера"),
    ("money", "Деньги и бизнес"),
    ("purchase", "Крупные покупки и аренда"),
    ("personal", "Быт и личное"),
]

DIFFICULTY_LABELS = {
    1: "1 — оппонент сам хочет договориться",
    2: "2 — упирается в несколько принципов, остальное обсуждаемо",
    3: "3 — действует строго по своим принципам, ответ свободным текстом",
}

CUSTOM_MIN_LEN = 30
CUSTOM_MAX_LEN = 400

LINE = "─" * 70


class ApiError(Exception):
    def __init__(self, status, detail):
        self.status, self.detail = status, detail
        super().__init__(f"{status}: {detail}")


def api(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
    request = urllib.request.Request(f"{BASE_URL}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            detail = json.loads(raw).get("detail", raw)
        except json.JSONDecodeError:
            detail = raw
        if isinstance(detail, list):  # ошибка валидации от FastAPI
            detail = "; ".join(str(item.get("msg", item)) for item in detail)
        raise ApiError(e.code, detail)
    except urllib.error.URLError as e:
        raise SystemExit(
            f"Не могу подключиться к {BASE_URL} ({e.reason}).\n"
            "Запущен ли сервер? В другом окне: uvicorn main:app --reload"
        )


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nПока.")
        raise SystemExit(0)


def ask_choice(prompt: str, allowed: list) -> str:
    while True:
        answer = ask(prompt)
        if answer in allowed:
            return answer
        print(f"   Нужно одно из: {', '.join(allowed)}")


def ensure_access_token() -> None:
    """Достаёт access_token (из .play_token или спрашивает) и проверяет его
    об сервер: если он просрочен/невалиден — переспрашивает."""
    global ACCESS_TOKEN

    if TOKEN_FILE.exists():
        ACCESS_TOKEN = TOKEN_FILE.read_text(encoding="utf-8").strip() or None

    while True:
        if not ACCESS_TOKEN:
            print("\nНужен access_token из Supabase Auth (вход по magic link).")
            ACCESS_TOKEN = ask("Вставь токен: ")
        try:
            api("GET", "/user/me")   # 404 — нормально (профиля ещё нет), 401 — токен плохой
            break
        except ApiError as e:
            if e.status == 404:
                break
            if e.status == 401:
                print(f"Токен не подошёл: {e.detail}")
                ACCESS_TOKEN = None
                continue
            raise

    TOKEN_FILE.write_text(ACCESS_TOKEN, encoding="utf-8")


def get_player() -> dict:
    """Профиль текущего (из токена) пользователя — создаёт при первом входе."""
    try:
        return api("GET", "/user/me")
    except ApiError as e:
        if e.status != 404:
            raise
        player = api("POST", "/user", {})
        print("Новый игрок создан.")
        return player


def show_progress(player: dict) -> None:
    to_next = player["xp_to_next_level"]
    tail = f", до следующего уровня {to_next} XP" if to_next else ", максимальный уровень"
    print(f"\nУровень {player['level']}, опыт {player['xp']}{tail}")
    print(f"Открытые сложности: {', '.join(map(str, player['unlocked_difficulties']))}")


def choose_mode() -> str:
    print("\nСитуация:")
    print("  1. Готовая тема")
    print("  2. Своя ситуация (описать своими словами)")
    return "theme" if ask_choice("Выбери 1/2: ", ["1", "2"]) == "1" else "custom"


def choose_theme() -> str:
    print("\nТема переговоров:")
    for i, (_, title) in enumerate(THEMES, 1):
        print(f"  {i}. {title}")
    choice = ask_choice("Выбери 1-4: ", [str(i) for i in range(1, len(THEMES) + 1)])
    return THEMES[int(choice) - 1][0]


def choose_custom_situation() -> str:
    print(f"\nОпишите ситуацию своими словами ({CUSTOM_MIN_LEN}-{CUSTOM_MAX_LEN} символов):")
    print("с кем вы договариваетесь и о чём именно.")
    while True:
        text = ask("> ")
        if CUSTOM_MIN_LEN <= len(text) <= CUSTOM_MAX_LEN:
            return text
        print(f"   Нужно от {CUSTOM_MIN_LEN} до {CUSTOM_MAX_LEN} символов, сейчас {len(text)}.")


def choose_difficulty(unlocked: list) -> int:
    print("\nСложность:")
    for level, label in DIFFICULTY_LABELS.items():
        mark = "" if level in unlocked else f"   (закрыта, откроется на уровне {level})"
        print(f"  {label}{mark}")
    allowed = [str(d) for d in unlocked]
    return int(ask_choice(f"Выбери {'/'.join(allowed)}: ", allowed))


def show_scenario(start: dict) -> None:
    print(f"\n{LINE}")
    print(start["scenario_text"])
    print(f"\nПротив тебя: {start['counterpart_role']}")
    print(f"Манера: {start['counterpart_tone']}")
    print(f"Его цель: {start['counterpart_goal']}")
    print(LINE)
    print(f"\nОппонент: {start['counterpart_opening']}")


def player_answer(options) -> dict:
    """Возвращает тело запроса для хода: вариант или свободный текст."""
    if not options:
        while True:
            message = ask("\nТвой ответ: ")
            if message:
                return {"message": message}
            print("   Пустой ответ не принимается.")

    print("\nВарианты ответа:")
    for option in options:
        print(f"  [{option['option_id']}] {option['text']}")
    ids = [option["option_id"] for option in options]
    return {"option_id": ask_choice(f"Выбери {'/'.join(ids)}: ", ids)}


def print_feedback(feedback) -> None:
    """feedback — обычно структурный объект (5 полей), но если модель дважды
    не собрала схему, движок деградирует его до простой строки (см. README,
    раздел "Структурный разбор диалога"). Проверяем тип, а не полагаемся на dict.
    """
    if isinstance(feedback, str):
        print("(!) feedback деградировал до простого текста (схема дважды не собралась):")
        print(f"    {feedback}")
        return
    if feedback.get("broke_quote"):
        print(f"  Где сломалось: «{feedback['broke_quote']}»")
        print(f"  Почему: {feedback['broke_reason']}")
    if feedback.get("what_worked"):
        print(f"  Что сработало: {feedback['what_worked']}")
    if feedback.get("alternative_phrasing"):
        print(f"  Как стоило сказать: {feedback['alternative_phrasing']}")
    print(f"  Совет: {feedback['tip']}")


def show_result(result: dict) -> None:
    verdict = "УСПЕХ" if result["outcome"] == "success" else "ПРОВАЛ"
    score = f", оценка {result['score']}/10" if result.get("score") is not None else ""
    print(f"\n{LINE}")
    print(f"{verdict}{score}\n")
    print_feedback(result["feedback"])
    print(f"\nПолучено {result['xp_gained']} XP. Всего {result['xp']}, уровень {result['level']}.")
    if result.get("level_up"):
        print(">>> Новый уровень! Открылась следующая сложность.")
    print(LINE)


def play_one(unlocked: list) -> None:
    mode = choose_mode()
    if mode == "custom":
        body = {"mode": "custom", "custom_situation": choose_custom_situation()}
    else:
        body = {"mode": "theme", "theme": choose_theme()}
    body["difficulty"] = choose_difficulty(unlocked)

    print("\nГенерирую сценарий, это занимает несколько секунд...")
    try:
        start = api("POST", "/negotiation/start", body)
    except ApiError as e:
        print(f"\nНе получилось начать: {e.detail}")
        return

    if start.get("rejected"):
        # Не ошибка сервера — сценарий не собрать из этого текста. Возврат
        # значением, а не исключением: см. README, раздел "Коды отказа".
        print(f"\n{start.get('message', 'Не получилось построить сценарий по этому описанию.')}")
        return

    show_scenario(start)
    token = start["session_token"]
    options = start.get("options")
    turn = 0

    while True:
        turn += 1
        body = {"session_token": token, **player_answer(options)}

        print("\nОппонент думает...")
        try:
            result = api("POST", "/negotiation/turn", body)
        except ApiError as e:
            print(f"\nОшибка на ходу {turn}: {e.detail}")
            if e.status in (400, 403, 409):
                print("Эти переговоры придётся начать заново.")
            return

        print(f"\nОппонент: {result['counterpart_reply']}")

        if not result["continue"]:
            show_result(result)
            return

        token = result["session_token"]
        options = result.get("options")


def main() -> None:
    print(f"Тренажёр переговоров — консольная версия\nСервер: {BASE_URL}")
    ensure_access_token()
    player = get_player()

    while True:
        show_progress(player)
        play_one(player["unlocked_difficulties"])

        # перечитываем прогресс из базы, чтобы увидеть реальное состояние
        player = api("GET", "/user/me")

        if ask_choice("\nЕщё раз? (y/n): ", ["y", "n", "д", "н"]) in ("n", "н"):
            show_progress(player)
            print("\nПока.")
            return


if __name__ == "__main__":
    main()
