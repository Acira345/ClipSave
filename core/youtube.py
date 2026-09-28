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

# Límite de videos a analizar de una playlist, para no colgar la app con
# listas gigantes (una de 500 videos tardaría muchísimo en analizarse
# uno por uno). Se puede subir más adelante si hace falta.
MAX_VIDEOS_PLAYLIST = 50


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


def analizar_entrada(url: str, progreso_callback=None) -> dict:
    """
    Analiza una URL que puede ser un solo video o una playlist completa.

    Devuelve:
      - {"tipo": "video", "info": {...}}  si es un solo video
      - {"tipo": "playlist", "titulo": str, "videos": [info, info, ...]}
        si es una playlist (cada elemento de "videos" es un dict de
        metadata completo, igual al que devuelve analizar_url, con
        calidades y tamaños reales — no una versión "plana"/resumida)

    progreso_callback(actual, total), si se pasa, se llama después de
    analizar cada video de la playlist, para poder mostrar algo como
    "Analizando 3 de 20..." en la interfaz mientras tarda.
    """
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": "in_playlist"}) as ydl:
        info_plano = ydl.extract_info(url, download=False)

    entradas = info_plano.get("entries")
    if not entradas:
        return {"tipo": "video", "info": analizar_url(url)}

    entradas = list(entradas)[:MAX_VIDEOS_PLAYLIST]
    videos = []
    total = len(entradas)
    for i, entrada in enumerate(entradas, start=1):
        video_url = entrada.get("url") or f"https://www.youtube.com/watch?v={entrada.get('id')}"
        try:
            videos.append(analizar_url(video_url))
        except Exception:
            pass  # Video privado/borrado/etc: se salta, no tumba el análisis completo
        if progreso_callback:
            progreso_callback(i, total)

    return {"tipo": "playlist", "titulo": info_plano.get("title", "Playlist"), "videos": videos}


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
        opciones.append({"label": f"{altura}p (~{total_mb:.1f} MB)", "height": altura, "tamaño_mb": total_mb})

    if not opciones:
        # Sin datos de tamaño disponibles (YouTube no siempre los da) — se
        # deja tamaño_mb en 0 para que no rompa la suma del total estimado,
        # simplemente no aporta nada a esa cuenta.
        opciones.append({"label": "Mejor disponible", "height": None, "tamaño_mb": 0})

    return opciones


def obtener_opciones_mp3(info: dict) -> list[dict]:
    """
    Arma la lista de bitrates de MP3 disponibles con tamaño estimado.
    Cada opción es un dict: {"label": str, "bitrate": int, "tamaño_mb": float}.
    """
    duracion = info.get("duration", 0)
    opciones = []
    for bitrate in MP3_BITRATES:
        size_mb = (bitrate * duracion) / 8192
        label = f"{bitrate} kbps (~{size_mb:.1f} MB)" if size_mb > 0 else f"{bitrate} kbps"
        opciones.append({"label": label, "bitrate": bitrate, "tamaño_mb": size_mb})
    return opciones


def estimar_tamaño_wav_mb(info: dict) -> float:
    """Estimación de tamaño para WAV (sin pérdida, sin compresión):
    calidad estándar 44.1kHz/16-bit estéreo, ~10.09 MB por minuto."""
    duracion = info.get("duration", 0) or 0
    return (duracion * 176400) / (1024 * 1024)


def estimar_tamaño_total_mb(opciones_por_video: list[float]) -> float:
    """Suma simple de los tamaños estimados (en MB) de una lista de videos,
    para mostrar 'esto va a pesar ~X MB/GB en total' antes de descargar."""
    return sum(opciones_por_video)


def formatear_tamaño(mb: float) -> str:
    """Da formato legible a un tamaño en MB: '842.3 MB' o '2.1 GB' si es grande."""
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.1f} MB"


def construir_opciones_descarga(
    download_path: str,
    tipo: str,
    valor_calidad,
    progress_hook=None,
) -> dict:
    """
    Construye el diccionario de opciones para yt_dlp según el tipo
    de descarga ("video", "mp3" o "wav") y el valor de calidad elegido
    (altura en px para video, bitrate en kbps para mp3, ignorado para wav
    ya que es sin pérdida; None = mejor disponible).
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

    if tipo in ("mp3", "wav"):
        postprocessor = {"key": "FFmpegExtractAudio", "preferredcodec": tipo}
        if tipo == "mp3":
            postprocessor["preferredquality"] = str(valor_calidad)
        opts.update({
            "format": "bestaudio/best",
            # Sin esto, yt_dlp puede dejar el archivo original (.webm/.m4a)
            # junto al .mp3/.wav ya convertido en vez de borrarlo.
            "keepvideo": False,
            "postprocessors": [postprocessor],
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


def predecir_ruta_final(download_path: str, tipo: str, info: dict) -> str:
    """
    Calcula la ruta completa donde va a quedar el archivo una vez
    terminada la descarga (con la extensión final: mp3 o mp4), para
    poder revisar de antemano si ya existe un archivo con ese nombre.
    """
    ext_final = tipo if tipo in ("mp3", "wav") else "mp4"
    outtmpl = os.path.join(download_path, "%(title)s.%(ext)s")
    with yt_dlp.YoutubeDL({"outtmpl": outtmpl, "quiet": True, "no_warnings": True}) as ydl:
        nombre_base = ydl.prepare_filename(info)
    raiz, _ = os.path.splitext(nombre_base)
    return f"{raiz}.{ext_final}"


def descargar(url: str, opts: dict) -> None:
    """Ejecuta la descarga con las opciones ya construidas."""
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])