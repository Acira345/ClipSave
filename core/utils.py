"""
Funciones auxiliares de formato. Puro cálculo, sin dependencias
de interfaz gráfica ni de yt_dlp.
"""

import os


def bytes_to_mb(size_bytes: float) -> float:
    """Convierte bytes a megabytes."""
    return (size_bytes or 0) / (1024 * 1024)


def format_duration(seconds: int) -> str:
    """Convierte segundos a formato MM:SS."""
    if not seconds:
        return "??:??"
    minutos = int(seconds) // 60
    segundos = int(seconds) % 60
    return f"{minutos:02}:{segundos:02}"


def format_size_mb(size_bytes: float) -> str:
    """Devuelve un tamaño en MB formateado, ej. '12.3 MB'."""
    return f"{bytes_to_mb(size_bytes):.1f} MB"


def truncate_path(path: str, length: int = 30) -> str:
    """Recorta una ruta larga para mostrarla en la UI, ej. '...Descargas/Videos'."""
    if len(path) <= length:
        return path
    return f"...{path[-length:]}"


def abrir_carpeta(path: str) -> None:
    """Abre una carpeta en el explorador de archivos de Windows."""
    os.startfile(path)  # noqa: this módulo se usa solo en Windows