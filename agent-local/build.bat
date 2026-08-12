@echo off
REM Gera dist\agent-local.exe a partir de agent-local.spec.
REM Executar a partir da pasta agent-local, com o .venv do projecto disponivel.

setlocal

if not exist ".venv\Scripts\python.exe" (
    echo [erro] .venv nao encontrado. Cria o ambiente virtual primeiro:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

echo [1/2] A verificar PyInstaller...
".venv\Scripts\python.exe" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller nao encontrado no .venv — a instalar...
    ".venv\Scripts\pip.exe" install pyinstaller
    if errorlevel 1 (
        echo [erro] Falha ao instalar o PyInstaller.
        exit /b 1
    )
)

echo [2/2] A gerar o executavel...
".venv\Scripts\python.exe" -m PyInstaller agent-local.spec --noconfirm
if errorlevel 1 (
    echo [erro] Build falhou.
    exit /b 1
)

echo.
echo Executavel gerado em: dist\agent-local.exe
endlocal
