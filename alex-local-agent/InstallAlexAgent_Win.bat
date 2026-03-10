@echo off
REM =====================================================================
REM Alex Agent — Windows Installer ^& Launcher
REM =====================================================================
REM Dublu-click pe acest fisier pentru a instala si porni Alex Agent.
REM Prima rulare: instalare automata (~3 minute, o singura data)
REM Rulari ulterioare: pornire imediata
REM =====================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ==========================================
echo   Alex Agent -- Installer
echo ==========================================
echo.

REM ── Check Python ─────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo [EROARE] Python nu este instalat!
        echo.
        echo Descarca de la: https://www.python.org/downloads/
        echo IMPORTANT: Bifeaza "Add Python to PATH" la instalare!
        echo.
        start https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set PYTHON=python3
) else (
    set PYTHON=python
)

for /f "tokens=2" %%v in ('!PYTHON! --version') do set PY_VER=%%v
echo [OK] Python !PY_VER! gasit

REM ── Create virtualenv ─────────────────────────────────────────────────────
set VENV_DIR=%~dp0.venv

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo.
    echo Prima rulare -- instalare componente ~3 minute...
    echo.

    echo [1/4] Creare mediu virtual Python...
    !PYTHON! -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [EROARE] Nu s-a putut crea virtualenv
        pause
        exit /b 1
    )

    echo [2/4] Instalare pachete...
    "%VENV_DIR%\Scripts\pip" install --quiet --upgrade pip
    "%VENV_DIR%\Scripts\pip" install --quiet ^
        "requests>=2.31.0" ^
        "playwright>=1.44.0" ^
        "pystray>=0.19.5" ^
        "pillow>=10.0.0" ^
        "python-dotenv>=1.0.0"
    if errorlevel 1 (
        echo [EROARE] pip install esuat
        pause
        exit /b 1
    )

    echo [3/4] Instalare browser Chromium ~150MB, o singura data...
    "%VENV_DIR%\Scripts\playwright" install chromium
    if errorlevel 1 (
        echo [ATENTIE] Chromium install a esuat - browser automation nu va functiona
    )

    echo [4/4] Instalare completa!
    echo.
    echo [OK] Alex Agent instalat cu succes!
) else (
    echo [OK] Instalare existenta gasita
    "%VENV_DIR%\Scripts\pip" install --quiet --upgrade requests playwright pystray pillow >nul 2>&1
)

REM ── Configure if needed ────────────────────────────────────────────────────
set CONFIG_DIR=%USERPROFILE%\.alex-agent
set CONFIG_FILE=%CONFIG_DIR%\config.json

if not exist "%CONFIG_FILE%" (
    mkdir "%CONFIG_DIR%" 2>nul

    echo.
    echo ==========================================
    echo   Configurare Alex Agent
    echo ==========================================
    echo.
    echo   Introdu datele primite de la administrator:
    echo.

    set /p ALEX_URL="  Alex URL [Enter pentru default]: "
    if "!ALEX_URL!"=="" set ALEX_URL=https://insurance-broker-alex-603810013022.europe-west3.run.app

    set /p API_KEY="  API Key: "
    if "!API_KEY!"=="" (
        echo.
        echo [ATENTIE] API Key nu poate fi gol. Ruleaza din nou dupa ce primesti cheia.
        pause
        exit /b 1
    )

    for /f %%i in ('!PYTHON! -c "import uuid,socket; print(socket.gethostname()+'-'+str(uuid.uuid4())[:8])"') do set AGENT_ID=%%i

    (
    echo {
    echo   "alex_url": "!ALEX_URL!",
    echo   "api_key": "!API_KEY!",
    echo   "poll_interval": 3,
    echo   "task_timeout": 120,
    echo   "headless_browser": true,
    echo   "gemini_api_key": "",
    echo   "anthropic_api_key": "",
    echo   "log_level": "INFO",
    echo   "agent_id": "!AGENT_ID!"
    echo }
    ) > "%CONFIG_FILE%"

    echo.
    echo [OK] Configurare salvata!
    echo     Agent ID: !AGENT_ID!
)

REM ── Show status ───────────────────────────────────────────────────────────
for /f "tokens=*" %%a in ('"%VENV_DIR%\Scripts\python" -c "import json; d=json.load(open(r'%CONFIG_FILE%')); print(d.get('alex_url',''))"') do set ALEX_URL=%%a
for /f "tokens=*" %%a in ('"%VENV_DIR%\Scripts\python" -c "import json; d=json.load(open(r'%CONFIG_FILE%')); print(d.get('agent_id',''))"') do set AGENT_ID=%%a

echo.
echo ==========================================
echo   Alex Agent pornind...
echo ==========================================
echo   Server:   !ALEX_URL!
echo   Agent ID: !AGENT_ID!
echo   Log:      %CONFIG_DIR%\agent.log
echo.
echo   Apasa Ctrl+C pentru a opri.
echo ==========================================
echo.

REM ── Start agent ───────────────────────────────────────────────────────────
set PYTHONPATH=%~dp0
"%VENV_DIR%\Scripts\python" "%~dp0agent_app.py" headless
if errorlevel 1 (
    echo.
    echo [EROARE] Agentul s-a oprit cu eroare. Verifica log-ul:
    echo   %CONFIG_DIR%\agent.log
    pause
)
