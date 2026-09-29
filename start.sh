#!/usr/bin/env bash
# Запуск «Арены переговоров» одной командой: бэкенд (FastAPI) + фронтенд (Vite).
#   ./start.sh          полный запуск, нужен .env с ключами
#   ./start.sh --demo   демо без ключей и бэкенда (заглушка вместо ИИ)
set -euo pipefail
cd "$(dirname "$0")"

FRONTEND_URL="http://127.0.0.1:5173"
BACKEND_URL="http://127.0.0.1:8000"
DEMO=0
[ "${1:-}" = "--demo" ] && DEMO=1

say() { printf '\033[36m%s\033[0m\n' "$1"; }
fail() { printf '\n\033[31m[!] %s\033[0m\n' "$1"; exit 1; }

env_value() { grep -E "^[[:space:]]*$1[[:space:]]*=" "$2" | tail -1 | cut -d= -f2- | tr -d "\"' \r" || true; }
port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
file_hash() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

# ---------- Node.js ----------
command -v node >/dev/null 2>&1 || fail "Не найден Node.js. Установите LTS-версию с https://nodejs.org"
node_ok=$(node -e 'const [a,b]=process.versions.node.split(".").map(Number);console.log((a===20&&b>=19)||(a===22&&b>=12)||a>=23?1:0)')
[ "$node_ok" = 1 ] || fail "Нужен Node.js 20.19+ или 22.12+, а установлен $(node --version). Обновите с https://nodejs.org (LTS)."

# ---------- ключи ----------
if [ "$DEMO" = 0 ]; then
  if [ ! -f .env ]; then
    cp .env.example .env
    fail "Не было файла .env — создан пустой из .env.example. Положите в папку проекта .env с ключами (или заполните этот) и запустите снова. Посмотреть интерфейс без ключей: ./start.sh --demo"
  fi
  missing=""
  for key in SUPABASE_URL SUPABASE_KEY SUPABASE_JWT_SECRET OPENROUTER_API_KEY; do
    [ -n "$(env_value "$key" .env)" ] || missing="$missing $key"
  done
  [ -z "$missing" ] || fail "В .env не заполнены:$missing"

  # Фронту нужен свой frontend/.env — собираем его из VITE_* строк общего .env.
  if [ ! -f frontend/.env ]; then
    grep -E '^[[:space:]]*VITE_' .env | tr -d '\r' > frontend/.env || true
    say "Создан frontend/.env из VITE_* строк .env"
  fi
  for key in VITE_SUPABASE_URL VITE_SUPABASE_ANON_KEY; do
    [ -n "$(env_value "$key" frontend/.env)" ] || fail "В frontend/.env не заполнен $key (или удалите frontend/.env, чтобы он собрался из .env заново)"
  done
fi

# ---------- порты ----------
port_busy 5173 && fail "Порт 5173 занят — похоже, фронт уже запущен в другом окне. Закройте его и запустите снова."
if [ "$DEMO" = 0 ] && port_busy 8000; then
  fail "Порт 8000 занят — похоже, бэкенд уже запущен в другом окне. Закройте его и запустите снова."
fi

# ---------- зависимости бэкенда ----------
VENV_PY="venv/bin/python"
if [ "$DEMO" = 0 ]; then
  if [ ! -x "$VENV_PY" ]; then
    command -v python3 >/dev/null 2>&1 || fail "Не найден python3. Установите Python 3.10+ с https://www.python.org"
    python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
      || fail "Нужен Python 3.10+, а найден $(python3 --version)."
    say "Создаю виртуальное окружение venv ($(python3 --version))..."
    python3 -m venv venv || fail "Не удалось создать venv. На Debian/Ubuntu: sudo apt install python3-venv"
  fi
  # Ставим заново только если requirements.txt изменился с прошлого раза.
  req_hash=$(file_hash requirements.txt)
  if [ "$(cat venv/.requirements.sha256 2>/dev/null || true)" != "$req_hash" ]; then
    say "Ставлю зависимости бэкенда (в первый раз — пара минут)..."
    "$VENV_PY" -m pip install --disable-pip-version-check -q -r requirements.txt \
      || fail "Не удалось поставить зависимости бэкенда — см. сообщения выше."
    echo "$req_hash" > venv/.requirements.sha256
  fi
fi

# ---------- зависимости фронтенда ----------
lock_hash=$(file_hash frontend/package-lock.json)
if [ "$(cat frontend/node_modules/.package-lock.sha256 2>/dev/null || true)" != "$lock_hash" ]; then
  say "Ставлю зависимости фронтенда..."
  (cd frontend && npm ci --no-audit --no-fund) || fail "Не удалось поставить зависимости фронтенда — см. сообщения выше."
  echo "$lock_hash" > frontend/node_modules/.package-lock.sha256
fi

# ---------- запуск ----------
BACKEND_PID=""
cleanup() {
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  say "Остановлено."
}
trap cleanup EXIT
trap 'exit 130' INT TERM

if [ "$DEMO" = 0 ]; then
  say "Запускаю бэкенд на $BACKEND_URL ..."
  "$VENV_PY" -m uvicorn main:app --host 127.0.0.1 --port 8000 &
  BACKEND_PID=$!
  ready=0
  for _ in $(seq 1 60); do
    kill -0 "$BACKEND_PID" 2>/dev/null || fail "Бэкенд не запустился — причина в сообщениях выше (чаще всего неверные ключи в .env)."
    if curl -fsS -o /dev/null "$BACKEND_URL/" 2>/dev/null; then ready=1; break; fi
    sleep 0.5
  done
  [ "$ready" = 1 ] || fail "Бэкенд не ответил за 30 секунд."
fi

echo
[ "$DEMO" = 1 ] && say "ДЕМО-режим: вход и ИИ заменены заглушкой, ключи не нужны."
say "Открываю $FRONTEND_URL — остановить всё: Ctrl+C"
echo

cd frontend
if [ "$DEMO" = 1 ]; then
  node node_modules/vite/bin/vite.js --open --mode mock
else
  node node_modules/vite/bin/vite.js --open
fi
