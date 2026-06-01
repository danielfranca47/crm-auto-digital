@echo off
cd /d "%~dp0"

:: Verifica se .env existe
if not exist ".env" (
    echo [ERRO] Ficheiro .env nao encontrado.
    echo Copia .env.example para .env e preenche a ANTHROPIC_API_KEY.
    pause
    exit /b 1
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
