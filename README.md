# bolshie-chleni

Backend API тренажёра переговоров: FastAPI + Qwen через OpenRouter + Supabase.

Диалог ведёт AI-модуль (`ai/`, точка входа — `presets.py`), бэкенд отвечает за
игрока: доступ к сложностям, начисление XP и уровни.

## Запуск

```bash
git clone https://github.com/matthew-dot-tyr/arena-negotiations-backend
cd arena-negotiations-backend

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # заполнить ключи
uvicorn main:app --reload
```

Документация и ручные запросы: http://127.0.0.1:8000/docs

Один раз на проект Supabase накатить миграции из `migrations/`
(SQL Editor → New query → вставить файл → Run), по порядку:

| Файл | Что создаёт |
|---|---|
| `001_users.sql` | таблицу `users` и функцию `add_xp` для атомарного начисления |
| `002_negotiations.sql` | таблицу `finished_negotiations` — защита от повторного начисления |

## Переменные окружения

| Переменная | Обязательна | Зачем |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_KEY` | да | база игроков |
| `OPENROUTER_API_KEY` | да | доступ к модели |
| `QWEN_MODEL` | нет | модель, по умолчанию `qwen/qwen3.8-flash-20260826` |
| `QWEN_START_MAX_TOKENS`, `QWEN_TURN_MAX_TOKENS` | нет | потолок длины ответа модели |
| `OPENROUTER_PROXY` | нет | если интернет только через VPN/прокси |
| `SESSION_SECRET` | на деплое | ключ подписи состояния переговоров |
| `CORS_ORIGINS` | нет | домены фронтенда через запятую |
| `XP_PER_LEVEL` | нет | шаг уровня в XP, по умолчанию 100 |

Реальный `.env` в гит не коммитим, ключи передаём в личке.

Без `SESSION_SECRET` ключ подписи генерируется случайным на время работы
процесса: после перезапуска сервера незакрытые переговоры придётся начать
заново, а несколько воркеров не поймут подписи друг друга.

## Как идут переговоры

Сценарии и историю диалога мы нигде не храним. Состояние уходит клиенту
в `session_token` (подписанная строка) и возвращается следующим запросом как
есть. Клиенту его читать и менять не нужно — подпись не сойдётся.

```
POST /negotiation/start  ->  сценарий, первая реплика, session_token, options
POST /negotiation/turn   ->  continue: true  — реплика оппонента, новый session_token
                             continue: false — итог, оценка, XP
```

### POST /negotiation/start

```json
{ "user_id": "...", "theme": "work", "difficulty": 1 }
```

Темы: `work`, `money`, `purchase`, `personal`. Сложность 1-3, но **не выше
уровня игрока** — иначе 403.

Ответ: `negotiation_id`, `session_token`, `scenario_text`, `counterpart_opening`,
`counterpart_role/tone/goal`, `max_turns`, а на сложностях 1-2 ещё и `options`.

### POST /negotiation/turn

```json
{ "user_id": "...", "session_token": "...", "option_id": "a" }
```

На сложности 3 вместо `option_id` — `message` со свободным текстом.

Пока диалог идёт:

```json
{ "continue": true, "counterpart_reply": "...", "session_token": "...", "options": [...] }
```

Когда переговоры закончились:

```json
{
  "continue": false,
  "counterpart_reply": "...",
  "outcome": "success",
  "score": 9,
  "feedback_text": "...",
  "xp_gained": 45,
  "xp": 45,
  "level": 1,
  "level_up": false
}
```

Число ходов игрока ограничено сложностью: 1 — 2-3 хода, 2 — 4-5, 3 — 6-7.
Диалог может закончиться раньше, если игрок отвечает плохо.

## Эндпоинты игрока

| Метод | Путь | Что делает |
|---|---|---|
| `POST` | `/user` | создаёт игрока (id можно не передавать) |
| `GET` | `/user/{id}` | xp, уровень, сколько до следующего, открытые сложности |
| `GET` | `/scenarios` | CRUD старого SQLite-слоя (наследие, под удаление) |

## Коды ошибок

| Код | Когда |
|---|---|
| 400 | плохой `option_id`, испорченный `session_token`, ошибка контракта движка |
| 403 | сложность закрыта либо токен принадлежит другому игроку |
| 409 | эти переговоры уже засчитаны |
| 422 | невалидное тело запроса |
| 503 | модель не ответила или вернула мусор после повторов |

## Начисление XP

- провал: фиксированно 5 XP
- успех: `score × множитель сложности`, множители `{1: 5, 2: 8, 3: 12}` — см. `progress.py`
- уровень из суммарного XP: 100 XP — 2 уровень, 200 XP — 3 (максимум)

В `ai/xp.py` лежит более старая формула (`score × difficulty × 2`). Бэкенд её
не вызывает, единственный источник правды — `progress.py`.

## Тесты

```bash
pytest -q
```

Тесты не ходят в Supabase и не тратят токены: база и движок подменяются
заглушками (`conftest.py` и фикстуры). Отдельно есть ручные проверки:

```bash
python test_offline.py            # движок ai/ без ключа
python test_presets_offline.py    # интерфейс presets.py без ключа
python test_live.py               # живой диалог, нужен ключ
python check_quality.py           # тон по сложностям и стабильность оценок, нужен ключ
python -m scripts.check_progress  # прогресс по реальной базе
```

## Структура

| Файл | Ответственность |
|---|---|
| `main.py` | эндпоинты переговоров, CORS, подключение роутеров |
| `routers/users.py` | эндпоинты игрока |
| `session_token.py` | подпись состояния переговоров |
| `progress.py` | уровни, формула XP, доступ к сложностям |
| `schemas.py` | Pydantic-схемы, слаги тем |
| `db.py` | Supabase: игроки, XP, засчитанные переговоры |
| `config.py` | переменные окружения сервера |
| `presets.py` | интерфейс AI-модуля для бэкенда |
| `prompts.py` | псевдонимы промптов, читать перед правкой `ai/prompts.py` |
| `ai/` | движок диалога: промпты, контракты, RAG, вызов модели |
| `migrations/` | SQL для Supabase |
| `app/` | старый SQLite-слой, остался от первой версии |
