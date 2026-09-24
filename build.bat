@echo off
REM =====================================================================
REM  Compila ClipSave en una carpeta autocontenida (modo --onedir) que
REM  funciona sin instalar nada (ni Python, ni librerias, ni ffmpeg) en
REM  la PC de quien la reciba.
REM
REM  Se usa --onedir en vez de --onefile a proposito: un .exe "onefile"
REM  se autoextrae a una carpeta temporal cada vez que se abre, y eso
REM  hace que antivirus como Windows Defender lo marquen como falso
REM  positivo (se parece al comportamiento de un troyano). En modo
REM  --onedir todo ya esta extraido de entrada, así que no dispara esa
REM  alerta.
REM
REM  Requisitos ANTES de correr esto (una sola vez, en TU pc):
REM    1) pip install -r requirements.txt
REM    2) Descargar ffmpeg (build "essentials", Windows) desde:
REM       https://www.gyan.dev/ffmpeg/builds/
REM       Copiar el ffmpeg.exe (esta dentro de la carpeta /bin del zip)
REM       a: clipsave\bin\ffmpeg.exe   <- crea esa carpeta si no existe
REM    3) (Opcional) tener icono.ico en la raiz del proyecto
REM
REM  PyInstaller se instala solo mas abajo si falta, no hace falta
REM  instalarlo a mano.
REM =====================================================================

echo Verificando PyInstaller...
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo No se encontro PyInstaller. Instalandolo...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo.
        echo [ERROR] No se pudo instalar PyInstaller. Revisa que Python
        echo y pip esten instalados y accesibles desde esta terminal.
        pause
        exit /b 1
    )
)

if not exist "bin\ffmpeg.exe" (
    echo.
    echo [ERROR] No se encontro bin\ffmpeg.exe
    echo Descargalo de https://www.gyan.dev/ffmpeg/builds/ y colocalo ahi
    echo antes de compilar. Sin el, la app no podra fusionar video/audio.
    pause
    exit /b 1
)

echo.
echo Compilando (esto puede tardar uno o dos minutos)...
python -m PyInstaller main.py ^
    --name ClipSave ^
    --onedir ^
    --windowed ^
    --icon icono.ico ^
    --add-binary "bin\ffmpeg.exe;bin" ^
    --add-data "icono.ico;." ^
    --collect-data customtkinter

if errorlevel 1 (
    echo.
    echo [ERROR] La compilacion fallo. Revisa el mensaje de arriba.
    pause
    exit /b 1
)

if not exist "dist\ClipSave\ClipSave.exe" (
    echo.
    echo [ERROR] PyInstaller termino pero no se genero dist\ClipSave\ClipSave.exe
    pause
    exit /b 1
)

echo.
echo Listo. La app quedo en la carpeta dist\ClipSave
echo IMPORTANTE: ya NO es un solo .exe. Comprime toda la carpeta dist\ClipSave
echo en un .zip y ese .zip es lo que le mandas a tu amigo. El debe descomprimirla
echo completa (no solo sacar el .exe) y correr ClipSave.exe desde adentro.
pause
