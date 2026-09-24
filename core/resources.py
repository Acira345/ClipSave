"""
Resuelve rutas a recursos (ffmpeg, íconos, etc.) que deben funcionar
tanto corriendo el proyecto con `python main.py` como ya compilado
con PyInstaller (donde los archivos viven en una carpeta temporal
distinta, sys._MEIPASS).
"""

import os
import sys


def resource_path(relative_path: str) -> str:
    """
    Devuelve la ruta absoluta a un recurso, ya sea en desarrollo
    o dentro del .exe empacado con PyInstaller.
    """
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def ffmpeg_path() -> str | None:
    """
    Devuelve la ruta al ffmpeg.exe empacado junto al programa, si existe.
    Si no existe (ej. estás en Mac/Linux o no lo empacaste), devuelve None
    y yt_dlp intentará usar el ffmpeg del sistema (PATH) como respaldo.
    """
    candidate = resource_path(os.path.join("bin", "ffmpeg.exe"))
    return candidate if os.path.isfile(candidate) else None
