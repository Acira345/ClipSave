"""
Revisa si hay una versión más nueva de ClipSave publicada.

Funciona leyendo un archivo `version.json` que tú controlas (por ejemplo,
subido a tu repo de GitHub). No descarga ni ejecuta ningún instalador
automáticamente: solo informa a la interfaz si hay algo nuevo, y le
pasa el link para que el USUARIO decida abrirlo y actualizar manualmente.

Esto es intencional: un programa que se auto-descarga y se auto-ejecuta
es exactamente el patrón que hace que los antivirus lo marquen como
sospechoso. Dejar la descarga en manos del usuario es más simple, más
transparente y no agrava el problema que ya tuviste con el antivirus.
"""

import requests

# Reemplaza esta URL cuando subas el proyecto a GitHub. Debe apuntar a
# un archivo version.json "en crudo" (raw), por ejemplo:
#   https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/version.json
#
# Formato esperado del archivo version.json:
#   {
#     "version": "1.1.0",
#     "url": "https://github.com/TU_USUARIO/TU_REPO/releases/latest"
#   }
VERSION_CHECK_URL = "https://raw.githubusercontent.com/Acira345/ClipSave/main/version.json"


def _version_a_tupla(version_str: str) -> tuple:
    """Convierte '1.10.2' en (1, 10, 2) para poder comparar versiones bien
    (una comparación de texto simple fallaría, ej. '1.9' vs '1.10')."""
    partes = []
    for parte in version_str.strip().split("."):
        try:
            partes.append(int(parte))
        except ValueError:
            partes.append(0)
    return tuple(partes)


def buscar_actualizacion(version_actual: str) -> dict | None:
    """
    Consulta VERSION_CHECK_URL y devuelve un dict {"version": ..., "url": ...}
    si hay una versión más nueva que `version_actual`. Devuelve None si ya
    estás en la última versión, o si no se pudo consultar (sin internet,
    URL no configurada todavía, etc. — nunca lanza un error hacia afuera,
    para que un fallo de red no interrumpa el uso normal de la app).
    """
    try:
        resp = requests.get(VERSION_CHECK_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        version_remota = data.get("version", "")
        if _version_a_tupla(version_remota) > _version_a_tupla(version_actual):
            return {"version": version_remota, "url": data.get("url", "")}
    except Exception:
        pass  # Sin internet, URL sin configurar, JSON mal formado, etc.

    return None
