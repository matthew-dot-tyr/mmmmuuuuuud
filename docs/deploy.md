# Деплой: бэкенд на Render, фронт на Vercel

База уже в облаке Supabase, миграции накатаны — её не трогаем. Выносим два куска:

| Что | Куда | Адрес будет вида |
|---|---|---|
| бэкенд (FastAPI) | Render, бесплатный план | `https://arena-api-xxxx.onrender.com` |
| фронт (`frontend/`) | Vercel, бесплатный план | `https://arena-xxxx.vercel.app` |

Оба сервиса сами пересобираются после каждого пуша в `main`.

## 0. Код в `main`

Render и Vercel берут код из ветки `main`. Сначала смёржить в неё `feat/frontend` (PR на GitHub → Merge).

## 1. Бэкенд → Render

1. Зайти на render.com через GitHub и дать доступ к репозиторию (он приватный — Render попросит разрешение).
2. **New → Blueprint** → выбрать репозиторий. Render найдёт `render.yaml` в корне.
3. Render попросит значения переменных — взять из своего `.env` бэкенда:

   | Переменная | Значение |
   |---|---|
   | `SUPABASE_URL` | как в `.env` |
   | `SUPABASE_KEY` | как в `.env` |
   | `SUPABASE_JWT_SECRET` | как в `.env` |
   | `OPENROUTER_API_KEY` | как в `.env` |
   | `QWEN_MODEL` | как в `.env` |
   | `CORS_ORIGINS` | пока `*`, заменим на шаге 3 |

   `SESSION_SECRET` вводить не нужно — Render сгенерирует его сам.
4. **Apply**. Первая сборка идёт 3–5 минут.
5. Проверка: открыть адрес сервиса. Должно прийти `{"message":"Arena Negotiations API is running!", ...}`.

## 2. Фронт → Vercel

1. Зайти на vercel.com через GitHub → **Add New → Project** → импортировать репозиторий.
2. **Root Directory: `frontend`** (кнопка Edit рядом с именем папки). Framework Vercel определит сам — Vite.
3. **Environment Variables:**

   | Переменная | Значение |
   |---|---|
   | `VITE_API_URL` | адрес бэкенда с Render, без `/` в конце |
   | `VITE_SUPABASE_URL` | как в `frontend/.env` |
   | `VITE_SUPABASE_ANON_KEY` | как в `frontend/.env` (anon-ключ, не service_role) |

4. **Deploy**. Сборка — около минуты.

`VITE_*` зашиваются в сборку. Если поменять их потом — нужен **Redeploy** в Vercel.

## 3. Связать

1. **Render** → сервис `arena-api` → Environment → `CORS_ORIGINS` = адрес фронта на Vercel (например `https://arena-xxxx.vercel.app`) → Save. Сервис перезапустится сам.
2. **Supabase** → Authentication → URL Configuration:
   - **Site URL** — адрес фронта на Vercel;
   - **Redirect URLs** — добавить адрес фронта на Vercel. `http://127.0.0.1:5173` оставить, чтобы работала локальная разработка.

## 4. Проверить

Открыть адрес фронта, ввести почту, перейти по ссылке из письма, пройти бой. Можно с телефона — теперь всё работает из любой точки.

## Что нужно знать

- **Бесплатный Render засыпает** после 15 минут без запросов. Первый запрос после паузы ждёт 30–50 секунд — экран загрузки просто висит дольше. Лечится платным планом (Render → сервис → Settings → Instance Type) — `render.yaml` менять не нужно.
- **Логи и ошибки бэкенда** — Render → сервис → Logs.
- **Свой домен** можно подключить позже и там и там (Settings → Domains). После этого обновить `CORS_ORIGINS` и адреса в Supabase.
- **Лимит по IP.** В `render.yaml` uvicorn запускается с `--forwarded-allow-ips="*"`, чтобы видеть настоящий IP игрока, а не прокси Render. Подделав заголовок, можно обойти лимит по IP, но лимиты на пользователя (по аккаунту) продолжают работать.
