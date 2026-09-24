"""
Toda la lógica relacionada con yt_dlp: analizar enlaces, calcular
calidades disponibles y armar las opciones de descarga.

Este módulo NO importa tkinter/customtkinter: es puramente lógico,
así que se puede probar o reutilizar (ej. en una CLI) sin la interfaz.
"""

import os
import shutil

import yt_dlp

from .resources import ffmpeg_path
from .utils import bytes_to_mb

MP3_BITRATES = [320, 256, 192, 128]


def ffmpeg_disponible() -> bool:
    """
    True si hay un ffmpeg utilizable: el que viene empacado junto al
    programa, o uno instalado en el sistema (PATH). Se usa para avisar
    con un mensaje claro ANTES de intentar descargar, en vez de que
    yt_dlp falle a mitad de la descarga con un error críptico.
    """
    return bool(ffmpeg_path() or shutil.which("ffmpeg"))


def analizar_url(url: str) -> dict:
    """
    Descarga la metadata de un video (sin descargar el archivo).
    Lanza una excepción si la URL no es válida o no se puede acceder.
    """
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        return ydl.extract_info(url, download=False)


def obtener_opciones_video(info: dict) -> list[dict]:
    """
    A partir de la metadata de un video, arma la lista de resoluciones
    disponibles. Cada opción es un dict: {"label": str, "height": int|None}.
    'height' es None cuando se trata de "Mejor disponible".
    """
    formatos = info.get("formats", [])

    best_audio = max(
        (f for f in formatos if f.get("vcodec") == "none" and f.get("acodec") != "none"),
        key=lambda x: x.get("filesize") or x.get("filesize_approx") or 0,
        default={},
    )
    audio_size = best_audio.get("filesize") or best_audio.get("filesize_approx") or 0

    resoluciones = {}
    for f in formatos:
        if f.get("vcodec") in ("none", None):
            continue
        altura = f.get("height")
        if not altura or not isinstance(altura, int):
            continue
        size = f.get("filesize") or f.get("filesize_approx") or 0
        if size > 0 and (altura not in resoluciones or size > resoluciones[altura]):
            resoluciones[altura] = size

    opciones = []
    for altura in sorted(resoluciones.keys(), reverse=True):
        total_mb = bytes_to_mb(resoluciones[altura] + audio_size)
        opciones.append({"label": f"{altura}p (~{total_mb:.1f} MB)", "height": altura})

    if not opciones:
        opciones.append({"label": "Mejor disponible", "height": None})

    return opciones


def obtener_opciones_mp3(info: dict) -> list[dict]:
    """
    Arma la lista de bitrates de MP3 disponibles con tamaño estimado.
    Cada opción es un dict: {"label": str, "bitrate": int}.
    """
    duracion = info.get("duration", 0)
    opciones = []
    for bitrate in MP3_BITRATES:
        size_mb = (bitrate * duracion) / 8192
        label = f"{bitrate} kbps (~{size_mb:.1f} MB)" if size_mb > 0 else f"{bitrate} kbps"
        opciones.append({"label": label, "bitrate": bitrate})
    return opciones


def construir_opciones_descarga(
    download_path: str,
    tipo: str,
    valor_calidad,
    progress_hook=None,
) -> dict:
    """
    Construye el diccionario de opciones para yt_dlp según el tipo
    de descarga ("video" o "mp3") y el valor de calidad elegido
    (altura en px para video, bitrate en kbps para mp3; None = mejor disponible).
    """
    ruta_salida = os.path.join(download_path, "%(title)s.%(ext)s")

    opts = {
        "outtmpl": ruta_salida,
        "quiet": True,
        "no_warnings": True,
        "nocolor": True,
    }
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    # Usa el ffmpeg empacado junto al programa si existe; si no,
    # yt_dlp caerá de vuelta al ffmpeg del PATH del sistema (o fallará
    # con un error claro si tampoco existe ahí).
    ruta_ffmpeg = ffmpeg_path()
    if ruta_ffmpeg:
        opts["ffmpeg_location"] = ruta_ffmpeg

    if tipo == "mp3":
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(valor_calidad),
            }],
        })
    else:  # video
        # Se prioriza el códec H.264 (avc1), que es el que reproducen
        # TODOS los dispositivos y reproductores sin necesidad de instalar
        # nada extra. Si YouTube no ofrece esa resolución en H.264, se cae
        # de vuelta a lo mejor disponible (que puede ser VP9 o AV1, más
        # nuevos pero no siempre soportados por reproductores viejos).
        if valor_calidad is None:
            formato = (
                "bestvideo[vcodec^=avc1]+bestaudio[ext=m4a]/"
                "bestvideo+bestaudio/best"
            )
        else:
            formato = (
                f"bestvideo[vcodec^=avc1][height<={valor_calidad}]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={valor_calidad}]+bestaudio/"
                f"best[height<={valor_calidad}]/best"
            )
        opts.update({
            "format": formato,
            "merge_output_format": "mp4",
        })

    return opts


def descargar(url: str, opts: dict) -> None:
    """Ejecuta la descarga con las opciones ya construidas."""
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
