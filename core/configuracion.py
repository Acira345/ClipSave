"""
Configuración persistente de ClipSave (preferencias del usuario), guardada
en %APPDATA%\\ClipSave\\config.json — la misma carpeta donde vive el
historial de descargas.
"""

import json
import os


def _ruta_config() -> str:
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    carpeta = os.path.join(base, "ClipSave")
    os.makedirs(carpeta, exist_ok=True)
    return os.path.join(carpeta, "config.json")


def cargar_config() -> dict:
    """Devuelve la configuración guardada, o {} si no existe todavía o
    el archivo está dañado."""
    ruta = _ruta_config()
    if not os.path.exists(ruta):
        return {}
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def guardar_config(config: dict) -> None:
    try:
        with open(_ruta_config(), "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # Si no se pudo guardar, la app sigue funcionando normal
