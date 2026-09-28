# АРЕНА ПЕРЕГОВОРОВ — фронтенд

React + Vite + `@supabase/supabase-js`. Внешний вид — `design/mockups.html`, поведение и работа с API — `design/DESIGN.md`, контракт API — `README.md` бэкенда.

## Запуск

Нужен Node.js 20+.

```bash
cd frontend
npm install
cp .env.example .env      # заполнить значения, см. ниже
npm run dev               # http://127.0.0.1:5173
```

Бэкенд должен быть запущен отдельно (`uvicorn main:app --reload` в корне репозитория).

### `.env`

| Переменная | Что это |
|---|---|
| `VITE_API_URL` | адрес бэкенда, по умолчанию `http://127.0.0.1:8000` |
| `VITE_SUPABASE_URL` | Supabase → Project Settings → API → Project URL |
| `VITE_SUPABASE_ANON_KEY` | там же, **anon / public** ключ. Не service_role и не `SUPABASE_KEY` из `.env` бэкенда |

Все `VITE_*` попадают в браузер — секретов сюда не класть.

### Настройка Supabase и бэкенда

- Supabase → Authentication → URL Configuration → **Redirect URLs**: добавить адрес фронта (`http://127.0.0.1:5173` для разработки, боевой домен для деплоя). Иначе ссылка из письма вернёт не туда.
- `.env` бэкенда → `CORS_ORIGINS`: адрес фронта (по умолчанию `*`, для деплоя лучше указать домен явно).

## Мок-режим

```bash
npm run dev:mock          # http://127.0.0.1:5173, без бэкенда и почты
```

Вход и API подменяются заглушкой `src/lib/mock.js`: после «Получить ссылку» появляется кнопка «Мок: открыть ссылку из письма». Удобно для вёрстки. Мок-сценарии:
- вариант ответа «a» или слово «сдаюсь» на сложности 3 — поражение, feedback строкой;
- «503» в тексте ответа — один раз ИИ «недоступен» (проверка «Повторить»);
- «плохо» / «непонятно» в своей ситуации — отказ `too_vague`.

Состояние мока лежит в `sessionStorage` вкладки. В продакшен-сборку мок не попадает.

## Сборка

```bash
npm run build             # в frontend/dist
npm run preview           # посмотреть сборку локально
```

Выкладка в интернет (Vercel) — [docs/deploy.md](../docs/deploy.md).

## Устройство

| Путь | Что там |
|---|---|
| `src/App.jsx` | сессия Supabase и переключение экранов |
| `src/screens/` | пять экранов: вход, профиль, подготовка, арена, итог |
| `src/components/Raccoon.jsx` | енот Торг (из `mockups.html`), эмоции `happy / stubborn / sly / sad` |
| `src/lib/api.js` | запросы к API с `Authorization: Bearer`, тексты ошибок от лица енота |
| `src/lib/supabase.js` | клиент Supabase, разбор токенов из ссылки magic link |
| `src/lib/game.js` | темы, сложности, формула XP для списка боёв |
| `src/styles.css` | токены цветов и все стили |

Поведение, которое легко сломать:
- `session_token` — всегда последний полученный; при `503` «Повторить» шлёт тот же запрос с тем же токеном.
- `feedback` бывает объектом или строкой (`src/components/Feedback.jsx`).
- `401` на любом запросе — выход на экран входа; `409` на ходе — возврат в профиль.
