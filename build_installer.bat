@echo off
REM =====================================================================
REM  Genera el instalador ClipSave-Setup.exe a partir de dist\ClipSave
REM  (que debe existir ya — corre primero build.bat).
REM
REM  Requiere Inno Setup instalado: https://jrsoftware.org/isdl.php
REM  (instalacion normal, con las opciones por defecto, basta).
REM =====================================================================

if not exist "dist\ClipSave\ClipSave.exe" (
    echo.
    echo [ERROR] No existe dist\ClipSave\ClipSave.exe
    echo Corre build.bat primero para generar la app.
    pause
    exit /b 1
)

set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if not exist %ISCC% (
    echo.
    echo [ERROR] No se encontro Inno Setup en la ruta esperada:
    echo %ISCC%
    echo Instalalo desde https://jrsoftware.org/isdl.php
    echo Si lo instalaste en otra carpeta, edita la variable ISCC en este archivo.
    pause
    exit /b 1
)

%ISCC% installer.iss

if errorlevel 1 (
    echo.
    echo [ERROR] Fallo la generacion del instalador. Revisa el mensaje de arriba.
    pause
    exit /b 1
)

echo.
echo Listo. El instalador quedo en Output\ClipSave-Setup.exe
echo Ese es el archivo que le mandas a la gente.
pause
