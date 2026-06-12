@echo off
cd /d "%~dp0"

:: Garante que o npm global (onde o Claude Code esta instalado) esta no PATH
set PATH=%APPDATA%\npm;%PATH%

:: Verifica se claude esta disponivel
where claude.cmd >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Claude Code nao encontrado em %APPDATA%\npm
    echo Garante que o Claude Code esta instalado: https://claude.ai/download
    pause
    exit /b 1
)

:: Cria .env a partir do exemplo se nao existir
if not exist ".env" (
    copy .env.example .env >nul
    echo [ADVISOR] .env criado a partir do .env.example
)

:: Cria virtualenv se nao existir
if not exist ".venv" (
    echo [ADVISOR] Criando ambiente virtual...
    python -m venv .venv
)

:: Activa o venv e instala dependencias
call .venv\Scripts\activate.bat

echo [ADVISOR] Verificando dependencias...
pip install -q -r requirements.txt

echo.
echo [ADVISOR] Iniciando servidor na porta 8005...
echo [ADVISOR] Dashboard: http://localhost:8005
echo.

python main.py

pause
