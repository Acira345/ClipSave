"""
Diálogos propios (error, advertencia, confirmación) con el estilo visual
de ClipSave, en vez de los cuadros de mensaje genéricos de Windows —
que se ven ajenos al resto de la app (ícono de Python, sin sus colores).
"""

import customtkinter as ctk

from ui import styles


def _crear_dialogo(parent, titulo, mensaje, icono, color_icono):
    dialogo = ctk.CTkToplevel(parent)
    dialogo.title(titulo)
    dialogo.resizable(False, False)
    dialogo.transient(parent)
    dialogo.configure(fg_color=styles.COLOR_BG_WHITE)

    contenido = ctk.CTkFrame(dialogo, fg_color="transparent")
    contenido.pack(fill="both", expand=True, padx=25, pady=20)

    cabecera = ctk.CTkFrame(contenido, fg_color="transparent")
    cabecera.pack(fill="x")
    ctk.CTkLabel(cabecera, text=icono, font=("Arial", 26), text_color=color_icono,
                 width=36).pack(side="left", padx=(0, 12))
    ctk.CTkLabel(cabecera, text=titulo, font=styles.FONT_SECTION,
                 text_color=styles.COLOR_TEXT_MAIN, wraplength=320, justify="left").pack(side="left", anchor="w")

    ctk.CTkLabel(contenido, text=mensaje, font=styles.FONT_LABEL_SMALL, text_color=styles.COLOR_TEXT_SECONDARY,
                 wraplength=360, justify="left").pack(fill="x", pady=(15, 0), anchor="w")

    # Centrar sobre la ventana principal y traer al frente
    dialogo.update_idletasks()
    ancho, alto = dialogo.winfo_reqwidth() + 10, dialogo.winfo_reqheight() + 10
    x = parent.winfo_x() + (parent.winfo_width() // 2) - (ancho // 2)
    y = parent.winfo_y() + (parent.winfo_height() // 2) - (alto // 2)
    dialogo.geometry(f"{ancho}x{alto}+{x}+{y}")
    dialogo.grab_set()
    dialogo.focus_force()

    return dialogo, contenido


def mostrar_error(parent, titulo, mensaje):
    dialogo, contenido = _crear_dialogo(parent, titulo, mensaje, "✕", styles.COLOR_PRIMARY)
    ctk.CTkButton(contenido, text="Aceptar", command=dialogo.destroy, fg_color=styles.COLOR_DARK,
                  hover_color=styles.COLOR_DARK_HOVER, width=100).pack(anchor="e", pady=(20, 0))
    dialogo.wait_window()


def mostrar_advertencia(parent, titulo, mensaje):
    dialogo, contenido = _crear_dialogo(parent, titulo, mensaje, "⚠", styles.COLOR_WARNING)
    ctk.CTkButton(contenido, text="Entendido", command=dialogo.destroy, fg_color=styles.COLOR_DARK,
                  hover_color=styles.COLOR_DARK_HOVER, width=100).pack(anchor="e", pady=(20, 0))
    dialogo.wait_window()


def confirmar(parent, titulo, mensaje, texto_confirmar="Reemplazar") -> bool:
    dialogo, contenido = _crear_dialogo(parent, titulo, mensaje, "?", styles.COLOR_WARNING)
    respuesta = {"valor": False}

    def _confirmar():
        respuesta["valor"] = True
        dialogo.destroy()

    botones = ctk.CTkFrame(contenido, fg_color="transparent")
    botones.pack(anchor="e", pady=(20, 0))
    ctk.CTkButton(botones, text="Cancelar", command=dialogo.destroy, fg_color="transparent",
                  text_color=styles.COLOR_TEXT_SECONDARY, hover_color=styles.COLOR_BORDER,
                  width=90).pack(side="left", padx=(0, 10))
    ctk.CTkButton(botones, text=texto_confirmar, command=_confirmar, fg_color=styles.COLOR_PRIMARY,
                  hover_color=styles.COLOR_PRIMARY_HOVER, width=110).pack(side="left")

    dialogo.wait_window()
    return respuesta["valor"]
