"""
Constantes de estilo: colores, fuentes y tamaños.
Centralizar esto acá permite cambiar el look de toda la app en un solo lugar.
"""

# Colores: cada uno es (color en modo claro, color en modo oscuro).
# customtkinter cambia automáticamente entre los dos cuando se llama a
# ctk.set_appearance_mode(), sin necesidad de reconfigurar cada widget.
# El color de marca (rojo) se deja fijo en ambos modos a propósito.
COLOR_PRIMARY = "#E74C3C"       # Rojo ClipSave — igual en ambos modos
COLOR_PRIMARY_HOVER = "#C0392B"
COLOR_DARK = ("#2C3E50", "#1A252F")
COLOR_DARK_HOVER = ("#1C2833", "#0F161C")
COLOR_SUCCESS = "#2ECC71"
COLOR_WARNING = "#F39C12"
COLOR_TEXT_MAIN = ("black", "#F5F5F5")
COLOR_TEXT_MUTED = ("#7F8C8D", "#9AA5AD")
COLOR_TEXT_SECONDARY = ("#566573", "#C5CBD1")
COLOR_TEXT_FAINT = ("#A6ACAF", "#6B7076")
COLOR_BORDER = ("#EBEDEF", "#3A3F44")
COLOR_BORDER_ALT = ("#D5DBDB", "#4A5058")
COLOR_BG_WHITE = ("white", "#242424")
COLOR_BG_LIGHT = ("#F8F9FA", "#2B2B2B")
COLOR_BG_CONTENT = ("#FBFCFC", "#1E1E1E")
COLOR_HOVER_LIGHT = ("#FADBD8", "#4A2C2A")

# Fuentes
FONT_LOGO = ("Arial", 22, "bold")
FONT_VERSION = ("Arial", 12)
FONT_STATUS = ("Arial", 12)
FONT_TITLE = ("Arial", 22, "bold")
FONT_SECTION = ("Arial", 14, "bold")
FONT_VIDEO_TITLE = ("Arial", 16, "bold")
FONT_LABEL_SMALL = ("Arial", 11)
FONT_YOUTUBE_TAG = ("Arial", 11, "bold")
FONT_BUTTON = ("Arial", 14, "bold")

# Animación
SPINNER_FRAMES = ["◐", "◓", "◑", "◒"]

# Tamaños
WINDOW_SIZE = "1200x750"
HEADER_HEIGHT = 60
RECENT_PANEL_WIDTH = 350
THUMBNAIL_HEIGHT = 90