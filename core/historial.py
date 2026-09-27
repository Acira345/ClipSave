"""
Historial de descargas: se guarda en un archivo JSON en la carpeta de
datos del usuario (%APPDATA%\\ClipSave\\historial.json), así sobrevive
a que cierres y vuelvas a abrir el programa.
"""

import json
import os
from datetime import datetime

MAX_ENTRADAS = 30


def _ruta_historial() -> str:
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    carpeta = os.path.join(base, "ClipSave")
    os.makedirs(carpeta, exist_ok=True)
    return os.path.join(carpeta, "historial.json")


def cargar_historial() -> list[dict]:
    """Devuelve la lista de descargas, más reciente primero. Si no hay
    historial todavía o el archivo está dañado, devuelve una lista vacía
    en vez de fallar."""
    ruta = _ruta_historial()
    if not os.path.exists(ruta):
        return []
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def agregar_entrada(titulo: str, tipo: str, ruta_archivo: str) -> list[dict]:
    """Agrega una descarga al inicio del historial, lo recorta a
    MAX_ENTRADAS y lo guarda. Devuelve el historial ya actualizado."""
    historial = cargar_historial()
    historial.insert(0, {
        "titulo": titulo,
        "tipo": tipo,
        "ruta": ruta_archivo,
        "fecha": datetime.now().strftime("%d/%m %H:%M"),
    })
    historial = historial[:MAX_ENTRADAS]
    try:
        with open(_ruta_historial(), "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return historial
