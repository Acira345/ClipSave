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

# Formatos disponibles por tipo. El orden es el orden en que se muestran
# los botones/dropdowns en la interfaz.
FORMATOS_AUDIO = ["MP3", "M4A", "OPUS", "OGG", "WAV"]
FORMATOS_VIDEO = ["MP4", "MKV"]

# De estos, solo MP3 y OGG tienen "calidad" ajustable (se recodifican a un
# bitrate elegido). M4A y OPUS se descargan en su formato nativo sin
# recodificar (yt_dlp evita la conversión si el códec ya coincide, así que
# es rápido y sin pérdida de calidad extra). WAV es sin pérdida por
# definición. Ninguno de estos tres tiene nada que "elegir".
FORMATOS_AUDIO_CON_CALIDAD = {"MP3", "OGG"}

# Códec de ffmpeg que le corresponde a cada formato de audio (para el
# postprocesador FFmpegExtractAudio) y la extensión final del archivo.
CODEC_POR_FORMATO_AUDIO = {"MP3": "mp3", "OGG": "vorbis", "M4A": "m4a", "OPUS": "opus", "WAV": "wav"}
EXT_POR_FORMATO_AUDIO = {"MP3": "mp3", "OGG": "ogg", "M4A": "m4a", "OPUS": "opus", "WAV": "wav"}

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


def obtener_opciones_calidad(info: dict, tipo: str, formato: str) -> list[dict]:
    """
    Punto de entrada único para calcular las opciones de calidad,
    cualquiera sea el tipo ("audio"/"video") y formato (MP3, MP4, etc.).

    Cada opción es un dict: {"label": str, "valor": int|None, "tamaño_mb": float}.
    'valor' es la altura en px (video) o el bitrate en kbps (audio con
    calidad ajustable: MP3/OGG). Para formatos "nativos"/sin pérdida
    (M4A, OPUS, WAV) no hay nada que elegir y 'valor' es siempre None.
    """
    if tipo == "video":
        return _opciones_calidad_video(info, formato)
    return _opciones_calidad_audio(info, formato)


def _opciones_calidad_video(info: dict, formato: str) -> list[dict]:
    formatos = info.get("formats", [])
    solo_mp4 = formato == "MP4"

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
        if solo_mp4 and f.get("ext") != "mp4":
            continue  # MP4 se queda solo con pistas ya en ese contenedor (H.264)
        altura = f.get("height")
        if not altura or not isinstance(altura, int):
            continue
        size = f.get("filesize") or f.get("filesize_approx") or 0
        if size > 0 and (altura not in resoluciones or size > resoluciones[altura]):
            resoluciones[altura] = size

    opciones = []
    for altura in sorted(resoluciones.keys(), reverse=True):
        total_mb = bytes_to_mb(resoluciones[altura] + audio_size)
        opciones.append({"label": f"{altura}p (~{total_mb:.1f} MB)", "valor": altura, "tamaño_mb": total_mb})

    if not opciones:
        # Sin datos de tamaño disponibles (YouTube no siempre los da) — se
        # deja tamaño_mb en 0 para que no rompa la suma del total estimado.
        opciones.append({"label": "Mejor disponible", "valor": None, "tamaño_mb": 0})

    return opciones


def _opciones_calidad_audio(info: dict, formato: str) -> list[dict]:
    if formato == "WAV":
        return [{"label": "Sin pérdida", "valor": None, "tamaño_mb": estimar_tamaño_wav_mb(info)}]

    if formato not in FORMATOS_AUDIO_CON_CALIDAD:
        # M4A / OPUS: formato nativo, sin recodificar — no hay bitrate que
        # elegir. Se estima el tamaño con la mejor pista de audio nativa
        # que YouTube ya ofrezca en ese códec.
        formatos = info.get("formats", [])
        mejor = max(
            (f for f in formatos if f.get("vcodec") in ("none", None) and f.get("acodec") != "none"),
            key=lambda x: x.get("abr") or 0,
            default={},
        )
        tam = bytes_to_mb(mejor.get("filesize") or mejor.get("filesize_approx") or 0)
        if tam == 0:
            abr = mejor.get("abr") or 128
            duracion = info.get("duration", 0) or 0
            tam = (abr * duracion) / 8192
        return [{"label": "Original (sin recodificar)", "valor": None, "tamaño_mb": tam}]

    # MP3 / OGG: calidad ajustable por bitrate, con re-encode
    duracion = info.get("duration", 0)
    opciones = []
    for bitrate in MP3_BITRATES:
        size_mb = (bitrate * duracion) / 8192
        label = f"{bitrate} kbps (~{size_mb:.1f} MB)" if size_mb > 0 else f"{bitrate} kbps"
        opciones.append({"label": label, "valor": bitrate, "tamaño_mb": size_mb})
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
    formato: str,
    valor_calidad,
    progress_hook=None,
) -> dict:
    """
    Construye el diccionario de opciones para yt_dlp.

    tipo: "audio" o "video"
    formato: para audio, uno de FORMATOS_AUDIO (MP3/M4A/OPUS/OGG/WAV);
             para video, uno de FORMATOS_VIDEO (MP4/MKV)
    valor_calidad: bitrate en kbps (audio con calidad ajustable) o altura
                   en px (video); None = mejor disponible / no aplica
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

    if tipo == "audio":
        codec = CODEC_POR_FORMATO_AUDIO[formato]
        # FFmpegExtractAudio, si la pista descargada ya viene en el códec
        # pedido (típico para M4A/OPUS, que se piden "nativos"), no
        # recodifica — solo la remuxea/renombra. Por eso M4A y OPUS salen
        # rápido y sin pérdida extra de calidad, aunque usen el mismo
        # postprocesador que MP3/OGG/WAV.
        postprocessor = {"key": "FFmpegExtractAudio", "preferredcodec": codec}
        if formato in FORMATOS_AUDIO_CON_CALIDAD and valor_calidad:
            postprocessor["preferredquality"] = str(valor_calidad)
        opts.update({
            "format": "bestaudio/best",
            # Sin esto, yt_dlp puede dejar el archivo original junto al
            # ya convertido, en vez de borrarlo.
            "keepvideo": False,
            "postprocessors": [postprocessor],
        })

    else:  # video
        if formato == "MP4":
            # H.264 (avc1) dentro de un contenedor mp4: máxima
            # compatibilidad, se reproduce en cualquier dispositivo sin
            # instalar nada extra. Si YouTube no la ofrece en esa
            # resolución, cae de vuelta a lo mejor disponible en mp4.
            if valor_calidad is None:
                formato_ytdlp = (
                    "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/"
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                )
            else:
                formato_ytdlp = (
                    f"bestvideo[ext=mp4][vcodec^=avc1][height<={valor_calidad}]+bestaudio[ext=m4a]/"
                    f"bestvideo[ext=mp4][height<={valor_calidad}]+bestaudio[ext=m4a]/"
                    f"best[ext=mp4][height<={valor_calidad}]/best"
                )
            opts.update({"format": formato_ytdlp, "merge_output_format": "mp4"})
        else:  # MKV: permite cualquier códec (VP9/AV1 incluidos), útil para 4K
            if valor_calidad is None:
                formato_ytdlp = "bestvideo+bestaudio/best"
            else:
                formato_ytdlp = f"bestvideo[height<={valor_calidad}]+bestaudio/best[height<={valor_calidad}]/best"
            opts.update({"format": formato_ytdlp, "merge_output_format": "mkv"})

    return opts


def predecir_ruta_final(download_path: str, tipo: str, formato: str, info: dict) -> str:
    """
    Calcula la ruta completa donde va a quedar el archivo una vez
    terminada la descarga (con su extensión final), para poder revisar
    de antemano si ya existe un archivo con ese nombre.
    """
    ext_final = EXT_POR_FORMATO_AUDIO[formato] if tipo == "audio" else formato.lower()
    outtmpl = os.path.join(download_path, "%(title)s.%(ext)s")
    with yt_dlp.YoutubeDL({"outtmpl": outtmpl, "quiet": True, "no_warnings": True}) as ydl:
        nombre_base = ydl.prepare_filename(info)
    raiz, _ = os.path.splitext(nombre_base)
    return f"{raiz}.{ext_final}"


def descargar(url: str, opts: dict) -> None:
    """Ejecuta la descarga con las opciones ya construidas."""
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])