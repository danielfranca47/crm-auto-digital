@echo off
REM Gera installer_output\DigitalPro-GeradorDeLeads-Setup.exe a partir de
REM agent-local-installer.iss. Garante primeiro que dist\agent-local.exe
REM esta actualizado (chama build.bat), depois compila o instalador com o
REM Inno Setup (ISCC.exe).

setlocal

call build.bat
if errorlevel 1 (
    echo [erro] build.bat falhou - instalador nao gerado.
    exit /b 1
)

set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"

if not exist "%ISCC%" (
    echo [erro] Inno Setup nao encontrado. Instala com:
    echo   winget install --id JRSoftware.InnoSetup -e
    exit /b 1
)

echo A gerar o instalador...
"%ISCC%" agent-local-installer.iss
if errorlevel 1 (
    echo [erro] Compilacao do instalador falhou.
    exit /b 1
)

echo.
echo Instalador gerado em: installer_output\DigitalPro-GeradorDeLeads-Setup.exe
endlocal
