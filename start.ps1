# Запуск «Арены переговоров» одной командой: бэкенд (FastAPI) + фронтенд (Vite).
#   .\start.ps1         полный запуск, нужен .env с ключами
#   .\start.ps1 -Demo   демо без ключей и бэкенда (заглушка вместо ИИ)
# Двойной клик по start.bat делает то же самое.
param([switch]$Demo)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location -LiteralPath $PSScriptRoot

$FrontendUrl = "http://127.0.0.1:5173"
$BackendUrl = "http://127.0.0.1:8000"
$RequiredKeys = @("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_JWT_SECRET", "OPENROUTER_API_KEY")
$RequiredViteKeys = @("VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY")

function Say($text) { Write-Host $text -ForegroundColor Cyan }
function Fail($text) {
    Write-Host ""
    Write-Host "[!] $text" -ForegroundColor Red
    exit 1
}

function Read-DotEnv($path) {
    $map = @{}
    foreach ($line in Get-Content -LiteralPath $path -Encoding UTF8) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $map[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'")
        }
    }
    return $map
}

function Test-Port($port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try { $client.Connect("127.0.0.1", $port); return $true }
    catch { return $false }
    finally { $client.Close() }
}

function Find-Python {
    $candidates = @(@("py", "-3"), @("python"), @("python3"))
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        $extra = @($candidate | Select-Object -Skip 1)
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $version = & $exe @extra -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        } catch { continue }
        if ($LASTEXITCODE -eq 0 -and $version) {
            return @{ Exe = $exe; Extra = $extra; Version = [version]"$version" }
        }
    }
    return $null
}

# ---------- Node.js ----------
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Fail "Не найден Node.js. Установите LTS-версию с https://nodejs.org и откройте новое окно терминала."
}
$nodeVersion = [version]((& node --version).TrimStart("v"))
$nodeOk = ($nodeVersion.Major -eq 20 -and $nodeVersion.Minor -ge 19) -or
          ($nodeVersion.Major -eq 22 -and $nodeVersion.Minor -ge 12) -or
          ($nodeVersion.Major -ge 23)
if (-not $nodeOk) {
    Fail "Нужен Node.js 20.19+ или 22.12+, а установлен $nodeVersion. Обновите с https://nodejs.org (LTS)."
}

# ---------- ключи ----------
if (-not $Demo) {
    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Fail "Не было файла .env — создан пустой из .env.example. Положите в папку проекта .env с ключами (или заполните этот) и запустите снова. Посмотреть интерфейс без ключей: .\start.ps1 -Demo"
    }
    $envMap = Read-DotEnv ".env"
    $missing = @($RequiredKeys | Where-Object { -not $envMap[$_] })
    if ($missing.Count -gt 0) { Fail "В .env не заполнены: $($missing -join ', ')" }

    # Фронту нужен свой frontend/.env — собираем его из VITE_* строк общего .env.
    if (-not (Test-Path "frontend\.env")) {
        $viteLines = @(Get-Content -LiteralPath ".env" -Encoding UTF8 | Where-Object { $_ -match '^\s*VITE_' })
        # Без BOM: Vite не распознаёт первую переменную, если файл начинается с BOM.
        [System.IO.File]::WriteAllLines((Join-Path $PSScriptRoot "frontend\.env"), [string[]]$viteLines, (New-Object System.Text.UTF8Encoding $false))
        Say "Создан frontend/.env из VITE_* строк .env"
    }
    $viteMap = Read-DotEnv "frontend\.env"
    $missingVite = @($RequiredViteKeys | Where-Object { -not $viteMap[$_] })
    if ($missingVite.Count -gt 0) { Fail "В frontend/.env не заполнены: $($missingVite -join ', ') (или удалите frontend/.env, чтобы он собрался из .env заново)" }
}

# ---------- порты ----------
if (Test-Port 5173) { Fail "Порт 5173 занят — похоже, фронт уже запущен в другом окне. Закройте его и запустите снова." }
if (-not $Demo -and (Test-Port 8000)) { Fail "Порт 8000 занят — похоже, бэкенд уже запущен в другом окне. Закройте его и запустите снова." }

# ---------- зависимости бэкенда ----------
$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not $Demo) {
    if (-not (Test-Path $venvPython)) {
        $python = Find-Python
        if (-not $python) { Fail "Не найден Python. Установите Python 3.10+ с https://www.python.org (галочка «Add python.exe to PATH») и откройте новое окно терминала." }
        if ($python.Version -lt [version]"3.10") { Fail "Нужен Python 3.10+, а найден $($python.Version)." }
        Say "Создаю виртуальное окружение venv (Python $($python.Version))..."
        & $python.Exe @($python.Extra) -m venv venv
        if ($LASTEXITCODE -ne 0) { Fail "Не удалось создать venv — см. сообщения выше." }
    }
    # Ставим заново только если requirements.txt изменился с прошлого раза.
    $reqHash = (Get-FileHash "requirements.txt").Hash
    $reqMarker = "venv\.requirements.sha256"
    if (-not (Test-Path $reqMarker) -or (Get-Content $reqMarker) -ne $reqHash) {
        Say "Ставлю зависимости бэкенда (в первый раз — пара минут)..."
        & $venvPython -m pip install --disable-pip-version-check -q -r requirements.txt
        if ($LASTEXITCODE -ne 0) { Fail "Не удалось поставить зависимости бэкенда — см. сообщения выше." }
        Set-Content -LiteralPath $reqMarker -Value $reqHash
    }
}

# ---------- зависимости фронтенда ----------
$lockHash = (Get-FileHash "frontend\package-lock.json").Hash
$lockMarker = "frontend\node_modules\.package-lock.sha256"
if (-not (Test-Path $lockMarker) -or (Get-Content $lockMarker) -ne $lockHash) {
    Say "Ставлю зависимости фронтенда..."
    Push-Location frontend
    & npm.cmd ci --no-audit --no-fund
    $npmCode = $LASTEXITCODE
    Pop-Location
    if ($npmCode -ne 0) { Fail "Не удалось поставить зависимости фронтенда — см. сообщения выше." }
    Set-Content -LiteralPath $lockMarker -Value $lockHash
}

# ---------- запуск ----------
$backend = $null
try {
    if (-not $Demo) {
        Say "Запускаю бэкенд на $BackendUrl ..."
        $backend = Start-Process -FilePath $venvPython -ArgumentList "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000" -NoNewWindow -PassThru
        $ready = $false
        for ($i = 0; $i -lt 60; $i++) {
            if ($backend.HasExited) { Fail "Бэкенд не запустился — причина в сообщениях выше (чаще всего неверные ключи в .env)." }
            try {
                Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri "$BackendUrl/" | Out-Null
                $ready = $true
                break
            } catch { Start-Sleep -Milliseconds 500 }
        }
        if (-not $ready) { Fail "Бэкенд не ответил за 30 секунд." }
    }

    Write-Host ""
    if ($Demo) { Say "ДЕМО-режим: вход и ИИ заменены заглушкой, ключи не нужны." }
    Say "Открываю $FrontendUrl — остановить всё: Ctrl+C"
    Write-Host ""

    Push-Location frontend
    $viteArgs = @("node_modules\vite\bin\vite.js", "--open")
    if ($Demo) { $viteArgs += @("--mode", "mock") }
    & node @viteArgs
} finally {
    Pop-Location -ErrorAction SilentlyContinue
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
    Say "Остановлено."
}
