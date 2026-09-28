"""
Interfaz gráfica de ClipSave.

Esta clase SOLO se encarga de construir la ventana, mostrar datos y
reaccionar a eventos del usuario. Toda la lógica de descarga (yt_dlp,
cálculo de calidades, etc.) vive en el paquete `core` y se invoca desde acá.
"""

import os
import threading
import tkinter as tk
import webbrowser
from io import BytesIO
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from core import configuracion, historial, thumbnails, updater, youtube
from core.resources import resource_path
from core.utils import abrir_carpeta, format_duration, truncate_path
from core.version import APP_VERSION
from ui import dialogs, styles

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("dark-blue")


class ClipSaveApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ClipSave - Descargador de YouTube")
        self.geometry(styles.WINDOW_SIZE)
        self.resizable(False, False)

        self._configurar_icono()

        # Aplica el modo claro/oscuro guardado de la última vez, ANTES de
        # construir los widgets, para que abran ya con el color correcto.
        self.config_guardada = configuracion.cargar_config()
        modo_oscuro_guardado = self.config_guardada.get("modo_oscuro", False)
        ctk.set_appearance_mode("Dark" if modo_oscuro_guardado else "Light")

        # Estado
        self.download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.current_video_info = None
        self.download_type = tk.StringVar(value="video")
        self.quality_options_map = {}  # label -> valor (height o bitrate)
        self._spinner_index = 0
        self._animando_spinner = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._construir_header()
        self._construir_contenido_principal()
        self._construir_panel_descargas()

        threading.Thread(target=self._hilo_buscar_actualizacion, daemon=True).start()

    # ------------------------------------------------------------------
    # Construcción de la UI
    # ------------------------------------------------------------------

    def _configurar_icono(self):
        try:
            import ctypes
            myappid = "diyel.clipsave.youtube.1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            self.iconbitmap(resource_path("icono.ico"))
        except Exception:
            pass  # Si falta el archivo, el programa sigue funcionando

    def _construir_header(self):
        self.header_frame = ctk.CTkFrame(
            self, height=styles.HEADER_HEIGHT, corner_radius=0,
            fg_color=styles.COLOR_BG_WHITE, border_width=1, border_color=styles.COLOR_BORDER,
        )
        self.header_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.header_frame.grid_propagate(False)

        try:
            logo_img = Image.open(resource_path("logo.png"))
            self.logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(32, 32))
            ctk.CTkLabel(self.header_frame, image=self.logo_ctk, text="").pack(side="left", padx=(30, 8), pady=15)
        except Exception:
            pass  # Si falta logo.png, la app sigue funcionando solo con el texto

        ctk.CTkLabel(self.header_frame, text="ClipSave", text_color=styles.COLOR_PRIMARY,
                     font=styles.FONT_LOGO).pack(side="left", padx=(0, 10), pady=15)
        ctk.CTkLabel(self.header_frame, text=APP_VERSION, text_color=styles.COLOR_TEXT_FAINT,
                     font=styles.FONT_VERSION).pack(side="left", pady=15)

        # Aviso de actualización disponible: arranca oculto, se muestra
        # solo si _hilo_buscar_actualizacion encuentra una versión nueva.
        self.update_label = ctk.CTkLabel(
            self.header_frame, text="", text_color=styles.COLOR_WARNING,
            font=styles.FONT_STATUS, cursor="hand2",
        )
        self.update_label.pack(side="left", padx=15, pady=15)

        self.status_label = ctk.CTkLabel(self.header_frame, text="● Listo",
                                          text_color=styles.COLOR_SUCCESS, font=styles.FONT_STATUS)
        self.status_label.pack(side="right", padx=30, pady=15)

        self.switch_modo_oscuro = ctk.CTkSwitch(
            self.header_frame, text="🌙", width=40, command=self._alternar_modo_oscuro,
            text_color=styles.COLOR_TEXT_SECONDARY, font=styles.FONT_STATUS,
            progress_color=styles.COLOR_DARK,
        )
        self.switch_modo_oscuro.pack(side="right", padx=(0, 10), pady=15)
        if self.config_guardada.get("modo_oscuro", False):
            self.switch_modo_oscuro.select()  # No dispara el command, así que no hay doble guardado

    def _alternar_modo_oscuro(self):
        modo_oscuro = bool(self.switch_modo_oscuro.get())
        ctk.set_appearance_mode("Dark" if modo_oscuro else "Light")
        self.config_guardada["modo_oscuro"] = modo_oscuro
        configuracion.guardar_config(self.config_guardada)

    def _construir_contenido_principal(self):
        self.main_content = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=styles.COLOR_BG_CONTENT)
        self.main_content.grid(row=1, column=0, sticky="nsew")

        ctk.CTkLabel(self.main_content, text="Descargar video", font=styles.FONT_TITLE,
                     text_color=styles.COLOR_TEXT_MAIN).pack(anchor="w", padx=30, pady=(30, 5))
        ctk.CTkLabel(self.main_content, text="Pega un enlace de YouTube y elige cómo quieres guardarlo.",
                     text_color=styles.COLOR_TEXT_MUTED).pack(anchor="w", padx=30, pady=(0, 20))

        self.search_frame = ctk.CTkFrame(self.main_content, fg_color=styles.COLOR_BG_WHITE, corner_radius=8,
                                          border_width=1, border_color=styles.COLOR_BORDER_ALT)
        self.search_frame.pack(fill="x", padx=30, pady=10)

        self.url_entry = ctk.CTkEntry(self.search_frame, placeholder_text="https://www.youtube.com/watch?v=...",
                                       fg_color="transparent", border_width=0, text_color=styles.COLOR_TEXT_MAIN, height=45)
        self.url_entry.pack(side="left", fill="x", expand=True, padx=10)
        self.url_entry.bind("<Return>", lambda e: self.analizar_url())
        self.url_entry.bind("<Button-3>", self._mostrar_menu_contextual)

        self.btn_analizar = ctk.CTkButton(self.search_frame, text="Analizar", command=self.analizar_url,
                                           fg_color=styles.COLOR_DARK, hover_color=styles.COLOR_DARK_HOVER,
                                           width=100, height=35)
        self.btn_analizar.pack(side="right", padx=(0, 10), pady=5)

        self.btn_refrescar = ctk.CTkButton(self.search_frame, text="⟳", command=self.reiniciar_formulario,
                                            fg_color="transparent", text_color=styles.COLOR_TEXT_SECONDARY,
                                            hover_color=styles.COLOR_BORDER, width=35, height=35,
                                            font=("Arial", 16))
        self.btn_refrescar.pack(side="right", padx=(0, 5), pady=5)

        self.preview_frame = ctk.CTkFrame(self.main_content, fg_color=styles.COLOR_BG_WHITE, corner_radius=12,
                                           border_width=1, border_color=styles.COLOR_BORDER)

    def _construir_panel_descargas(self):
        self.recent_frame = ctk.CTkFrame(self, width=styles.RECENT_PANEL_WIDTH, corner_radius=0,
                                          fg_color=styles.COLOR_BG_LIGHT, border_width=1, border_color=styles.COLOR_BORDER)
        self.recent_frame.grid(row=1, column=1, sticky="nsew")
        self.recent_frame.grid_propagate(False)

        ctk.CTkLabel(self.recent_frame, text="Historial", font=styles.FONT_SECTION,
                     text_color=styles.COLOR_TEXT_MAIN).pack(anchor="w", padx=20, pady=(20, 10))

        self.historial_frame = ctk.CTkScrollableFrame(self.recent_frame, fg_color="transparent")
        self.historial_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._refrescar_historial()

    def _refrescar_historial(self):
        for widget in self.historial_frame.winfo_children():
            widget.destroy()

        entradas = historial.cargar_historial()
        if not entradas:
            ctk.CTkLabel(self.historial_frame, text="Aquí van a aparecer tus últimas descargas.",
                         text_color=styles.COLOR_TEXT_MUTED, font=styles.FONT_LABEL_SMALL,
                         wraplength=250, justify="left").pack(fill="x", padx=10, pady=5)
            return

        for entrada in entradas:
            self._crear_item_historial(entrada)

    def _crear_item_historial(self, entrada: dict):
        icono = "🎵" if entrada["tipo"] in ("mp3", "wav") else "🎬"
        item = ctk.CTkFrame(self.historial_frame, fg_color=styles.COLOR_BG_WHITE, corner_radius=8, cursor="hand2")
        item.pack(fill="x", pady=4)

        contenido = ctk.CTkFrame(item, fg_color="transparent")
        contenido.pack(fill="x", padx=10, pady=8)

        fila_superior = ctk.CTkFrame(contenido, fg_color="transparent")
        fila_superior.pack(fill="x")
        ctk.CTkLabel(fila_superior, text=icono, font=("Arial", 14)).pack(side="left", padx=(0, 6))
        titulo = entrada["titulo"]
        if len(titulo) > 38:
            titulo = titulo[:38] + "..."
        ctk.CTkLabel(fila_superior, text=titulo, font=styles.FONT_LABEL_SMALL,
                     text_color=styles.COLOR_TEXT_MAIN, anchor="w").pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(contenido, text=entrada["fecha"], font=("Arial", 10),
                     text_color=styles.COLOR_TEXT_MUTED, anchor="w").pack(anchor="w", pady=(2, 0))

        # Click en cualquier parte del ítem abre la carpeta donde quedó el archivo
        for widget in (item, contenido, fila_superior):
            widget.bind("<Button-1>", lambda e, ruta=entrada["ruta"]: self._abrir_carpeta_de_historial(ruta))

    def _abrir_carpeta_de_historial(self, ruta_archivo: str):
        try:
            abrir_carpeta(os.path.dirname(ruta_archivo))
        except Exception:
            pass  # La carpeta pudo haberse movido o borrado desde entonces

    # ------------------------------------------------------------------
    # Análisis de URL (dispara lógica en core.youtube)
    # ------------------------------------------------------------------

    def reiniciar_formulario(self):
        """Limpia la URL, la previsualización y el progreso, sin reiniciar la app.
        También destraba el botón 'Analizar' por si se quedó pegado en el spinner
        (ej. una URL que nunca responde)."""
        self.url_entry.delete(0, tk.END)
        self.current_video_info = None
        self.preview_frame.pack_forget()
        if hasattr(self, "progress_bar"):
            self.progress_bar.set(0)
            self.progress_text.configure(text="Esperando enlace...")
        self._animando_spinner = False
        self.btn_analizar.configure(state="normal", text="Analizar")
        self.status_label.configure(text="● Listo", text_color=styles.COLOR_SUCCESS)

    def _mostrar_menu_contextual(self, event):
        # CTkEntry envuelve un tkinter.Entry interno (self.url_entry._entry);
        # los eventos <<Cut>>/<<Copy>>/<<Paste>> hay que mandarlos a ese
        # widget interno, no al CTkEntry de afuera, o si no no hacen nada.
        entry_interno = self.url_entry._entry
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Cortar", command=lambda: entry_interno.event_generate("<<Cut>>"))
        menu.add_command(label="Copiar", command=lambda: entry_interno.event_generate("<<Copy>>"))
        menu.add_command(label="Pegar", command=lambda: entry_interno.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(
            label="Seleccionar todo",
            command=lambda: (entry_interno.select_range(0, tk.END), entry_interno.icursor(tk.END)),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def analizar_url(self):
        url = self.url_entry.get()
        if not url:
            dialogs.mostrar_advertencia(self, "Falta la URL", "Por favor, pega una URL de YouTube.")
            return

        self.status_label.configure(text="● Analizando...", text_color=styles.COLOR_WARNING)
        self.btn_analizar.configure(state="disabled")
        self._animando_spinner = True
        self._animar_spinner_analizar()

        threading.Thread(target=self._hilo_analizar, args=(url,), daemon=True).start()

    def _animar_spinner_analizar(self):
        if not getattr(self, "_animando_spinner", False):
            return
        frame = styles.SPINNER_FRAMES[self._spinner_index % len(styles.SPINNER_FRAMES)]
        self.btn_analizar.configure(text=frame)
        self._spinner_index += 1
        self.after(120, self._animar_spinner_analizar)

    def _hilo_analizar(self, url):
        def progreso(actual, total):
            self.after(0, lambda: self.status_label.configure(
                text=f"● Analizando {actual}/{total}...", text_color=styles.COLOR_WARNING))

        try:
            resultado = youtube.analizar_entrada(url, progreso_callback=progreso)
            if resultado["tipo"] == "playlist":
                self.after(0, self._mostrar_previsualizacion_playlist, resultado)
            else:
                self.after(0, self._mostrar_previsualizacion, resultado["info"])
        except Exception as e:
            self.after(0, lambda: dialogs.mostrar_error(self, "No se pudo analizar", str(e)))
            self.after(0, self._resetear_busqueda)

    def _resetear_busqueda(self):
        self._animando_spinner = False
        self.status_label.configure(text="● Listo", text_color=styles.COLOR_SUCCESS)
        self.btn_analizar.configure(state="normal", text="Analizar")
        self.url_entry.delete(0, tk.END)

    # ------------------------------------------------------------------
    # Previsualización
    # ------------------------------------------------------------------

    def _mostrar_previsualizacion(self, info):
        self.current_video_info = info
        self._resetear_busqueda()

        for widget in self.preview_frame.winfo_children():
            widget.destroy()
        self.preview_frame.pack(fill="x", padx=30, pady=20)

        self._mostrar_info_basica(info)
        self._mostrar_selector_formato()
        self._mostrar_selector_ruta()
        self._mostrar_boton_descarga()

    # ------------------------------------------------------------------
    # Previsualización y descarga de PLAYLISTS
    # ------------------------------------------------------------------

    def _mostrar_previsualizacion_playlist(self, resultado):
        self._resetear_busqueda()

        for widget in self.preview_frame.winfo_children():
            widget.destroy()
        self.preview_frame.pack(fill="x", padx=30, pady=20)

        self.playlist_videos = resultado["videos"]
        self.playlist_tipo_actual = "video"

        ctk.CTkLabel(
            self.preview_frame, text=f"📃 {resultado['titulo']} ({len(self.playlist_videos)} videos)",
            font=styles.FONT_VIDEO_TITLE, text_color=styles.COLOR_TEXT_MAIN,
            wraplength=500, justify="left",
        ).pack(anchor="w", padx=15, pady=(15, 10))

        format_frame = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        format_frame.pack(fill="x", padx=15, pady=5)
        self.seg_button_playlist = ctk.CTkSegmentedButton(
            format_frame, values=["Video (MP4)", "Audio (MP3)", "Audio (WAV)"],
            command=self._cambiar_tipo_playlist, dynamic_resizing=False, width=390, height=35,
            fg_color=styles.COLOR_BORDER, selected_color=styles.COLOR_BORDER_ALT,
            unselected_color=styles.COLOR_BORDER, text_color=styles.COLOR_TEXT_MAIN,
        )
        self.seg_button_playlist.set("Video (MP4)")
        self.seg_button_playlist.pack(anchor="w")

        lista_frame = ctk.CTkScrollableFrame(self.preview_frame, height=280, fg_color=styles.COLOR_BG_LIGHT)
        lista_frame.pack(fill="x", padx=15, pady=15)

        self.playlist_filas = []
        for info_video in self.playlist_videos:
            self.playlist_filas.append(self._crear_fila_playlist(lista_frame, info_video))

        self._actualizar_calidad_playlist("video")
        self._mostrar_selector_ruta()
        self._mostrar_boton_descarga_playlist()

    def _crear_fila_playlist(self, lista_frame, info_video):
        fila = ctk.CTkFrame(lista_frame, fg_color="transparent")
        fila.pack(fill="x", pady=4)

        var_incluir = tk.BooleanVar(value=True)
        checkbox = ctk.CTkCheckBox(fila, text="", variable=var_incluir, width=20,
                                    command=self._al_cambiar_seleccion_playlist)
        checkbox.pack(side="left", padx=(0, 8))

        titulo = info_video.get("title", "Sin título")
        if len(titulo) > 45:
            titulo = titulo[:45] + "..."
        ctk.CTkLabel(fila, text=titulo, text_color=styles.COLOR_TEXT_MAIN, anchor="w",
                     width=280, wraplength=280, justify="left").pack(side="left", padx=(0, 8))

        opciones_video = youtube.obtener_opciones_video(info_video)
        opciones_mp3 = youtube.obtener_opciones_mp3(info_video)
        mapa_video = {op["label"]: op["height"] for op in opciones_video}
        mapa_mp3 = {op["label"]: op["bitrate"] for op in opciones_mp3}
        mapa_tam_video = {op["label"]: op["tamaño_mb"] for op in opciones_video}
        mapa_tam_mp3 = {op["label"]: op["tamaño_mb"] for op in opciones_mp3}
        mapa_tam_wav = {"Sin pérdida": youtube.estimar_tamaño_wav_mb(info_video)}

        combo = ctk.CTkComboBox(fila, values=list(mapa_video.keys()), width=180,
                                 fg_color=styles.COLOR_BG_WHITE, text_color=styles.COLOR_TEXT_MAIN,
                                 command=lambda _: self._al_cambiar_seleccion_playlist())
        combo.pack(side="left")

        return {"info": info_video, "incluir": var_incluir, "combo": combo,
                "mapa_video": mapa_video, "mapa_mp3": mapa_mp3,
                "mapa_tam_video": mapa_tam_video, "mapa_tam_mp3": mapa_tam_mp3, "mapa_tam_wav": mapa_tam_wav}

    def _cambiar_tipo_playlist(self, value):
        if "Video" in value:
            tipo = "video"
        elif "WAV" in value:
            tipo = "wav"
        else:
            tipo = "mp3"
        self._actualizar_calidad_playlist(tipo)

    def _actualizar_calidad_playlist(self, tipo):
        self.playlist_tipo_actual = tipo
        for fila in self.playlist_filas:
            combo = fila["combo"]
            if tipo == "video":
                labels = list(fila["mapa_video"].keys())
                combo.configure(state="normal", values=labels)
                combo.set(labels[0])
            elif tipo == "mp3":
                labels = list(fila["mapa_mp3"].keys())
                combo.configure(state="normal", values=labels)
                combo.set(labels[0])
            else:  # wav: sin pérdida, no hay calidad que elegir
                combo.configure(state="disabled", values=["Sin pérdida"])
                combo.set("Sin pérdida")
        self._al_cambiar_seleccion_playlist()

    def _al_cambiar_seleccion_playlist(self):
        """Se llama cada vez que cambia algo que afecta cuánto se va a
        descargar: marcar/desmarcar un video, cambiar su calidad, o
        cambiar el formato general. Actualiza el contador del botón y
        el tamaño total estimado."""
        if hasattr(self, "btn_descargar_playlist"):
            cantidad = sum(1 for f in self.playlist_filas if f["incluir"].get())
            self.btn_descargar_playlist.configure(text=f"Descargar seleccionados ({cantidad})")

        if hasattr(self, "playlist_total_label"):
            clave_mapa = f"mapa_tam_{self.playlist_tipo_actual}"
            total_mb = 0.0
            for fila in self.playlist_filas:
                if not fila["incluir"].get():
                    continue
                total_mb += fila[clave_mapa].get(fila["combo"].get(), 0)
            self.playlist_total_label.configure(
                text=f"Tamaño total estimado: ~{youtube.formatear_tamaño(total_mb)}")

    def _mostrar_boton_descarga_playlist(self):
        self.playlist_total_label = ctk.CTkLabel(
            self.preview_frame, text="Tamaño total estimado: calculando...",
            text_color=styles.COLOR_TEXT_SECONDARY, font=styles.FONT_LABEL_SMALL,
        )
        self.playlist_total_label.pack(anchor="w", padx=15, pady=(0, 8))
        self._al_cambiar_seleccion_playlist()

        cantidad = len(self.playlist_filas)
        self.btn_descargar_playlist = ctk.CTkButton(
            self.preview_frame, text=f"Descargar seleccionados ({cantidad})",
            command=self.iniciar_descarga_playlist, fg_color=styles.COLOR_PRIMARY,
            hover_color=styles.COLOR_PRIMARY_HOVER, font=styles.FONT_BUTTON, height=45,
        )
        self.btn_descargar_playlist.pack(fill="x", padx=15, pady=(0, 20))

        self.playlist_progress_frame = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        self.playlist_progress_bar = ctk.CTkProgressBar(
            self.playlist_progress_frame, progress_color=styles.COLOR_PRIMARY,
            fg_color=styles.COLOR_BORDER_ALT, height=12)
        self.playlist_progress_bar.set(0)
        self.playlist_progress_bar.pack(fill="x", pady=(0, 8))
        self.playlist_progress_label = ctk.CTkLabel(
            self.playlist_progress_frame, text="Iniciando descarga...",
            text_color=styles.COLOR_TEXT_MUTED, font=styles.FONT_LABEL_SMALL)
        self.playlist_progress_label.pack(anchor="w")

    def iniciar_descarga_playlist(self):
        if not youtube.ffmpeg_disponible():
            dialogs.mostrar_error(
                self, "Falta un componente",
                "No se encontró ffmpeg. Reinstala ClipSave con la versión más reciente "
                "del instalador, que ya lo incluye.",
            )
            return

        seleccionados = [f for f in self.playlist_filas if f["incluir"].get()]
        if not seleccionados:
            dialogs.mostrar_advertencia(self, "Nada seleccionado",
                                         "Marca al menos un video de la lista para descargar.")
            return

        tipo = self.playlist_tipo_actual
        tareas = []
        for fila in seleccionados:
            if tipo == "video":
                valor_calidad = fila["mapa_video"].get(fila["combo"].get())
            elif tipo == "mp3":
                valor_calidad = fila["mapa_mp3"].get(fila["combo"].get())
            else:
                valor_calidad = None
            tareas.append({"info": fila["info"], "valor_calidad": valor_calidad})

        self.btn_descargar_playlist.pack_forget()
        self.playlist_progress_bar.set(0)
        self.playlist_progress_label.configure(text="Iniciando descarga...")
        self.playlist_progress_frame.pack(fill="x", padx=15, pady=(0, 20))
        self.status_label.configure(text="● Descargando...", text_color=styles.COLOR_PRIMARY)

        threading.Thread(target=self._hilo_descarga_playlist, args=(tareas, tipo), daemon=True).start()

    def _hilo_descarga_playlist(self, tareas, tipo):
        total = len(tareas)
        fallidos = 0

        for i, tarea in enumerate(tareas, start=1):
            info_video = tarea["info"]
            titulo = info_video.get("title", "Sin título")
            self.after(0, lambda i=i, t=titulo: self.playlist_progress_label.configure(
                text=f"Video {i}/{total}: {t}"))
            self.after(0, lambda i=i: self.playlist_progress_bar.set((i - 1) / total))

            try:
                ruta_final = youtube.predecir_ruta_final(self.download_path, tipo, info_video)
                opts = youtube.construir_opciones_descarga(
                    self.download_path, tipo, tarea["valor_calidad"],
                    progress_hook=self._progress_hook_playlist(i, total, titulo),
                )
                youtube.descargar(info_video["webpage_url"], opts)
                historial.agregar_entrada(titulo, tipo, ruta_final)
            except Exception:
                fallidos += 1  # Video privado/borrado/error puntual: sigue con el resto

        self.after(0, self._finalizar_descarga_playlist, fallidos, total)

    def _progress_hook_playlist(self, indice, total, titulo):
        def hook(d):
            if d["status"] == "downloading":
                try:
                    descargado = d.get("downloaded_bytes") or 0
                    total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    progreso_video = (descargado / total_bytes) if total_bytes else 0
                    progreso_global = ((indice - 1) + progreso_video) / total
                    self.after(0, lambda p=progreso_global: self.playlist_progress_bar.set(p))
                except Exception:
                    pass
        return hook

    def _finalizar_descarga_playlist(self, fallidos, total):
        self.playlist_progress_frame.pack_forget()
        self._actualizar_texto_boton_playlist()
        self.btn_descargar_playlist.pack(fill="x", padx=15, pady=(0, 20))
        self.status_label.configure(text="● Listo", text_color=styles.COLOR_SUCCESS)
        self._refrescar_historial()
        try:
            abrir_carpeta(self.download_path)
        except Exception:
            pass
        if fallidos:
            dialogs.mostrar_advertencia(
                self, "Descarga completada con avisos",
                f"{fallidos} de {total} videos no se pudieron descargar "
                "(posiblemente privados, eliminados o restringidos).",
            )

    def _mostrar_info_basica(self, info):
        top_info_frame = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        top_info_frame.pack(fill="x", padx=15, pady=15)

        try:
            img_bytes = thumbnails.fetch_thumbnail_bytes(info["thumbnail"])
            img = Image.open(BytesIO(img_bytes))
            w, h = img.size
            new_w = int(styles.THUMBNAIL_HEIGHT * w / h)
            ctk_img = ctk.CTkImage(light_image=img, size=(new_w, styles.THUMBNAIL_HEIGHT))
            ctk.CTkLabel(top_info_frame, image=ctk_img, text="").pack(side="left", padx=(0, 15))
        except Exception:
            pass

        text_frame = ctk.CTkFrame(top_info_frame, fg_color="transparent")
        text_frame.pack(side="left", fill="y")

        ctk.CTkLabel(text_frame, text="YOUTUBE", text_color=styles.COLOR_PRIMARY,
                     font=styles.FONT_YOUTUBE_TAG).pack(anchor="w")
        ctk.CTkLabel(text_frame, text=info["title"], text_color=styles.COLOR_TEXT_MAIN,
                     font=styles.FONT_VIDEO_TITLE, wraplength=400, justify="left").pack(anchor="w")

        duracion = info.get("duration")
        if not duracion:
            texto_info = f"VOD / Stream | {info.get('width', '?')}x{info.get('height', '?')}"
        else:
            texto_info = f"{format_duration(duracion)} | {info.get('width', '?')}x{info.get('height', '?')}"
        ctk.CTkLabel(text_frame, text=texto_info, text_color=styles.COLOR_TEXT_MUTED).pack(anchor="w")

    def _mostrar_selector_formato(self):
        ctk.CTkLabel(self.preview_frame, text="Formato y calidad", font=styles.FONT_SECTION,
                     text_color=styles.COLOR_TEXT_MAIN).pack(anchor="w", padx=15, pady=(10, 5))

        format_frame = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        format_frame.pack(fill="x", padx=15, pady=5)

        self.seg_button = ctk.CTkSegmentedButton(
            format_frame, values=["Video (MP4)", "Audio (MP3)", "Audio (WAV)"], command=self._cambiar_tipo_descarga,
            dynamic_resizing=False, width=390, height=35,
            fg_color=styles.COLOR_BORDER, selected_color=styles.COLOR_BORDER_ALT,
            unselected_color=styles.COLOR_BORDER, text_color=styles.COLOR_TEXT_MAIN,
        )
        self.seg_button.set("Video (MP4)")
        self.seg_button.pack(anchor="w")

        self.quality_frame = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        self.quality_frame.pack(fill="x", padx=15, pady=(10, 15))

        self._actualizar_opciones_calidad("video")

    def _mostrar_selector_ruta(self):
        save_frame = ctk.CTkFrame(self.preview_frame, fg_color=styles.COLOR_BG_LIGHT, corner_radius=8, height=45)
        save_frame.pack(fill="x", padx=15, pady=10)
        save_frame.pack_propagate(False)

        self.path_label = ctk.CTkLabel(
            save_frame, text=f"📂 Guardar en: {truncate_path(self.download_path)}", text_color=styles.COLOR_TEXT_SECONDARY,
        )
        self.path_label.pack(side="left", padx=10)

        ctk.CTkButton(save_frame, text="Cambiar", command=self.cambiar_ruta, fg_color="transparent",
                      text_color=styles.COLOR_PRIMARY, hover_color=styles.COLOR_HOVER_LIGHT, width=60).pack(side="right", padx=10)

    def _mostrar_boton_descarga(self):
        self.btn_descargar_ya = ctk.CTkButton(
            self.preview_frame, text="Descargar ahora", command=self.iniciar_descarga,
            fg_color=styles.COLOR_PRIMARY, hover_color=styles.COLOR_PRIMARY_HOVER,
            font=styles.FONT_BUTTON, height=45,
        )
        self.btn_descargar_ya.pack(fill="x", padx=15, pady=20)

        # Ocupa el mismo lugar que el botón, pero arranca oculto: se
        # muestra en vez del botón mientras la descarga está en curso.
        self.progress_inline_frame = ctk.CTkFrame(self.preview_frame, fg_color="transparent")

        self.progress_bar = ctk.CTkProgressBar(self.progress_inline_frame, progress_color=styles.COLOR_PRIMARY,
                                                fg_color=styles.COLOR_BORDER_ALT, height=12)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 8))

        self.progress_text = ctk.CTkLabel(self.progress_inline_frame, text="Iniciando descarga...",
                                           text_color=styles.COLOR_TEXT_MUTED, font=styles.FONT_LABEL_SMALL,
                                           wraplength=500, justify="left")
        self.progress_text.pack(anchor="w")

    def _mostrar_barra_progreso(self):
        self.btn_descargar_ya.pack_forget()
        self.progress_bar.set(0)
        self.progress_text.configure(text="Iniciando descarga...")
        self.progress_inline_frame.pack(fill="x", padx=15, pady=20)

    def _ocultar_barra_progreso(self):
        self.progress_inline_frame.pack_forget()
        self.btn_descargar_ya.pack(fill="x", padx=15, pady=20)

    # ------------------------------------------------------------------
    # Selección de tipo y calidad (usa core.youtube para calcular opciones)
    # ------------------------------------------------------------------

    def _cambiar_tipo_descarga(self, value):
        if "Video" in value:
            self.download_type.set("video")
            self._actualizar_opciones_calidad("video")
        elif "WAV" in value:
            self.download_type.set("wav")
            self._actualizar_opciones_calidad("wav")
        else:
            self.download_type.set("mp3")
            self._actualizar_opciones_calidad("mp3")

    def _actualizar_opciones_calidad(self, tipo):
        for widget in self.quality_frame.winfo_children():
            widget.destroy()

        if tipo == "wav":
            # El WAV es sin pérdida: no hay bitrate que elegir, así que no
            # se muestra un dropdown, solo un aviso informativo.
            ctk.CTkLabel(self.quality_frame, text="🎼 Sin pérdida (WAV) — no requiere elegir calidad",
                         text_color=styles.COLOR_TEXT_SECONDARY).pack(anchor="w")
            self.quality_options_map = {}
            self.quality_dropdown = None
            return

        if tipo == "video":
            ctk.CTkLabel(self.quality_frame, text="Calidad de video", text_color=styles.COLOR_TEXT_SECONDARY).pack(anchor="w")
            opciones = youtube.obtener_opciones_video(self.current_video_info)
            clave = "height"
        else:
            ctk.CTkLabel(self.quality_frame, text="Calidad MP3 (CBR)", text_color=styles.COLOR_TEXT_SECONDARY).pack(anchor="w")
            opciones = youtube.obtener_opciones_mp3(self.current_video_info)
            clave = "bitrate"

        self.quality_options_map = {op["label"]: op[clave] for op in opciones}
        labels = list(self.quality_options_map.keys())

        self.quality_dropdown = ctk.CTkComboBox(self.quality_frame, values=labels, width=250,
                                                  fg_color=styles.COLOR_BG_WHITE, text_color=styles.COLOR_TEXT_MAIN)
        self.quality_dropdown.set(labels[0])
        self.quality_dropdown.pack(anchor="w", pady=5)

    # ------------------------------------------------------------------
    # Ruta de guardado
    # ------------------------------------------------------------------

    def cambiar_ruta(self):
        path = filedialog.askdirectory()
        if path:
            self.download_path = path
            self.path_label.configure(text=f"📂 Guardar en: {truncate_path(self.download_path)}")

    # ------------------------------------------------------------------
    # Descarga (arma opts con core.youtube y ejecuta en un hilo)
    # ------------------------------------------------------------------

    def iniciar_descarga(self):
        if not self.current_video_info:
            return

        if not youtube.ffmpeg_disponible():
            dialogs.mostrar_error(
                self, "Falta un componente",
                "No se encontró ffmpeg. Reinstala ClipSave con la versión más reciente "
                "del instalador, que ya lo incluye.",
            )
            return

        tipo = self.download_type.get()
        ruta_final = youtube.predecir_ruta_final(self.download_path, tipo, self.current_video_info)
        if os.path.exists(ruta_final):
            reemplazar = dialogs.confirmar(
                self, "El archivo ya existe",
                f"'{os.path.basename(ruta_final)}' ya existe en la carpeta de descargas.\n"
                "¿Quieres reemplazarlo?",
            )
            if not reemplazar:
                return

        self._mostrar_barra_progreso()
        self.status_label.configure(text="● Descargando...", text_color=styles.COLOR_PRIMARY)

        url = self.current_video_info["webpage_url"]
        # El WAV no tiene dropdown de calidad (self.quality_dropdown es None ahí)
        valor_calidad = None
        if self.quality_dropdown is not None:
            label_calidad = self.quality_dropdown.get()
            valor_calidad = self.quality_options_map.get(label_calidad)

        opts = youtube.construir_opciones_descarga(
            self.download_path, tipo, valor_calidad, progress_hook=self._progress_hook,
        )
        titulo = self.current_video_info.get("title", "Sin título")

        threading.Thread(target=self._hilo_descarga, args=(url, opts, titulo, tipo, ruta_final), daemon=True).start()

    def _hilo_descarga(self, url, opts, titulo, tipo, ruta_final):
        try:
            youtube.descargar(url, opts)
            try:
                abrir_carpeta(self.download_path)
            except Exception:
                pass  # Si no se pudo abrir la carpeta, no interrumpe el flujo de éxito
            historial.agregar_entrada(titulo, tipo, ruta_final)
            self.after(0, self._refrescar_historial)
        except Exception as e:
            mensaje_error = str(e)
            self.after(0, lambda m=mensaje_error: dialogs.mostrar_error(self, "Error al descargar", m))
        finally:
            self.after(0, self._finalizar_estado_descarga)

    def _finalizar_estado_descarga(self):
        self._ocultar_barra_progreso()
        self.status_label.configure(text="● Listo", text_color=styles.COLOR_SUCCESS)

    # ------------------------------------------------------------------
    # Actualizaciones
    # ------------------------------------------------------------------

    def _hilo_buscar_actualizacion(self):
        resultado = updater.buscar_actualizacion(APP_VERSION)
        if resultado:
            self.after(0, lambda: self._mostrar_aviso_actualizacion(resultado))

    def _mostrar_aviso_actualizacion(self, info):
        url = info["url"]
        self.update_label.configure(text=f"🔔 Nueva versión {info['version']} disponible")
        self.update_label.bind("<Button-1>", lambda e: webbrowser.open(url))

    def _progress_hook(self, d):
        if d["status"] == "downloading":
            try:
                downloaded = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0

                if total > 0:
                    progress = downloaded / total
                    dl_mb = downloaded / (1024 * 1024)
                    tot_mb = total / (1024 * 1024)
                    speed = d.get("_speed_str", "N/A")
                    texto = f"Descargando: {dl_mb:.1f} MB / {tot_mb:.1f} MB ({progress * 100:.1f}%) - {speed}"
                    self.after(0, lambda p=progress: self.progress_bar.set(p))
                else:
                    texto = f"Iniciando: {d.get('_downloaded_bytes_str', 'N/A')} - {d.get('_speed_str', 'N/A')}"

                self.after(0, lambda t=texto: self.progress_text.configure(text=t))
            except Exception:
                pass
        elif d["status"] == "finished":
            self.after(0, lambda: self.progress_text.configure(text="Procesando archivo final (uniendo audio/video)..."))
            self.after(0, lambda: self.progress_bar.set(1.0))