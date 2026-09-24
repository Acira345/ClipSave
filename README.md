# ClipSave

Descargador de YouTube a MP4 o MP3, simple y gratuito.

## Descargar

Ve a la sección [Releases](../../releases) de este repositorio y descarga
`ClipSave-Setup.exe` (o el `.zip`, según lo que hayas publicado). Instálalo
y listo — no necesitas Python ni nada más instalado en tu computadora.

## Aviso

ClipSave es una herramienta de uso personal. Es responsabilidad de quien
la usa respetar los derechos de autor del contenido que descarga y los
Términos de Servicio de la plataforma de origen. Este proyecto no aloja,
distribuye ni tiene ningún vínculo con contenido de terceros — únicamente
provee el programa.

## Para desarrolladores: correrlo desde el código

```
pip install -r requirements.txt
python main.py
```

Necesitas además colocar un `ffmpeg.exe` (Windows) en `bin/ffmpeg.exe`
para poder descargar video (unir audio+video) o convertir a MP3.
Descárgalo desde https://www.gyan.dev/ffmpeg/builds/ (build "essentials").

## Compilar tu propio instalador

```
build.bat              REM genera dist\ClipSave
build_installer.bat    REM genera Output\ClipSave-Setup.exe (requiere Inno Setup)
```

## Apoyar el proyecto

Si te resultó útil, espero que en un futuro tener una seccion de donaciones jeje

## Licencia

MIT
