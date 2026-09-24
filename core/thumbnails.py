"""
Obtiene los bytes de una imagen (miniatura) desde una URL.
No depende de tkinter: la UI decide cómo convertirla en un widget.
"""

import requests


def fetch_thumbnail_bytes(url: str) -> bytes:
    """Descarga una imagen y devuelve sus bytes crudos."""
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.content
