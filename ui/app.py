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
        self.cola_descargas = []  # cada item: {"info","tipo","formato","valor_calidad","titulo"}
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
        ctk.CTkLabel(self.main_content, text="Escribe el nombre del video o pega un enlace de YouTube y elige cómo quieres guardarlo.",
                     text_color=styles.COLOR_TEXT_MUTED).pack(anchor="w", padx=30, pady=(0, 20))

        self.search_frame = ctk.CTkFrame(self.main_content, fg_color=styles.COLOR_BG_WHITE, corner_radius=8,
                                          border_width=1, border_color=styles.COLOR_BORDER_ALT)
        self.search_frame.pack(fill="x", padx=30, pady=10)

        self.url_entry = ctk.CTkEntry(self.search_frame, placeholder_text="Pega un enlace de YouTube o busca por texto...",
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

        # --- Cola de Descargas: lo que vas agregando antes de bajarlo todo junto ---
        ctk.CTkLabel(self.recent_frame, text="Cola de descargas", font=styles.FONT_SECTION,
                     text_color=styles.COLOR_TEXT_MAIN).pack(anchor="w", padx=20, pady=(20, 10))

        self.cola_frame = ctk.CTkScrollableFrame(self.recent_frame, fg_color="transparent", height=220)
        self.cola_frame.pack(fill="x", padx=10, pady=(0, 5))

        self.btn_descargar_cola = ctk.CTkButton(
            self.recent_frame, text="Descargar lista (0)", command=self.iniciar_descarga_cola,
            fg_color=styles.COLOR_PRIMARY, hover_color=styles.COLOR_PRIMARY_HOVER,
            font=styles.FONT_BUTTON, height=38,
        )
        self.btn_descargar_cola.pack(fill="x", padx=20, pady=(0, 8))

        # Ocupa el mismo espacio que iría debajo del botón mientras se
        # descarga la lista completa; arranca oculto.
        self.cola_progress_frame = ctk.CTkFrame(self.recent_frame, fg_color="transparent")
        self.cola_progress_bar = ctk.CTkProgressBar(self.cola_progress_frame, progress_color=styles.COLOR_PRIMARY,
                                                     fg_color=styles.COLOR_BORDER_ALT, height=10)
        self.cola_progress_bar.set(0)
        self.cola_progress_bar.pack(fill="x", padx=20, pady=(0, 4))
        self.cola_progress_label = ctk.CTkLabel(self.cola_progress_frame, text="",
                                                 text_color=styles.COLOR_TEXT_MUTED, font=("Arial", 10))
        self.cola_progress_label.pack(anchor="w", padx=20)

        self._refrescar_cola()

        # --- Historial: lo que ya se descargó (como estaba) ---
        ctk.CTkLabel(self.recent_frame, text="Historial", font=styles.FONT_SECTION,
                     text_color=styles.COLOR_TEXT_MAIN).pack(anchor="w", padx=20, pady=(15, 10))

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
        icono = "🎵" if entrada["tipo"] == "audio" else "🎬"
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
            dialogs.mostrar_advertencia(self, "Campo vacío",
                                         "Escribe un término de búsqueda o pega una URL de YouTube.")
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
            resultado = youtube.procesar_busqueda(url, progreso_callback=progreso)
            if resultado["tipo"] == "playlist":
                self.after(0, self._mostrar_previsualizacion_playlist, resultado)
            elif resultado["tipo"] == "busqueda":
                self.after(0, self._mostrar_resultados_busqueda, resultado["resultados"])
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

    def _mostrar_resultados_busqueda(self, resultados):
        """Muestra hasta 5 tarjetas clicables cuando el usuario buscó por
        texto en vez de pegar una URL. Al hacer click en una, se reutiliza
        _mostrar_previsualizacion tal cual funciona para un video pegado
        directamente."""
        self._resetear_busqueda()

        for widget in self.preview_frame.winfo_children():
            widget.destroy()
        self.preview_frame.pack(fill="x", padx=30, pady=20)

        ctk.CTkLabel(self.preview_frame, text="Resultados de la búsqueda", font=styles.FONT_SECTION,
                     text_color=styles.COLOR_TEXT_MAIN).pack(anchor="w", padx=15, pady=(15, 10))

        if not resultados:
            ctk.CTkLabel(self.preview_frame, text="No se encontró nada con ese término.",
                         text_color=styles.COLOR_TEXT_MUTED).pack(anchor="w", padx=15, pady=(0, 15))
            return

        for info_resultado in resultados:
            self._crear_tarjeta_resultado(info_resultado)

        ctk.CTkLabel(self.preview_frame, text="", height=1).pack(pady=5)  # respiro final

    def _crear_tarjeta_resultado(self, info_resultado):
        tarjeta = ctk.CTkFrame(self.preview_frame, fg_color=styles.COLOR_BG_LIGHT, corner_radius=8, cursor="hand2")
        tarjeta.pack(fill="x", padx=15, pady=5)
        contenido = ctk.CTkFrame(tarjeta, fg_color="transparent")
        contenido.pack(fill="x", padx=12, pady=10)

        titulo = info_resultado.get("title", "Sin título")
        canal = info_resultado.get("uploader") or info_resultado.get("channel") or ""
        duracion = format_duration(info_resultado.get("duration"))

        ctk.CTkLabel(contenido, text=titulo, font=styles.FONT_VIDEO_TITLE, text_color=styles.COLOR_TEXT_MAIN,
                     anchor="w", wraplength=450, justify="left").pack(anchor="w")
        ctk.CTkLabel(contenido, text=f"{canal} · {duracion}", text_color=styles.COLOR_TEXT_MUTED,
                     anchor="w").pack(anchor="w", pady=(2, 0))

        for widget in (tarjeta, contenido):
            widget.bind("<Button-1>", lambda e, info=info_resultado: self._mostrar_previsualizacion(info))

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

        ctk.CTkLabel(
            self.preview_frame, text=f"📃 {resultado['titulo']} ({len(self.playlist_videos)} videos)",
            font=styles.FONT_VIDEO_TITLE, text_color=styles.COLOR_TEXT_MAIN,
            wraplength=500, justify="left",
        ).pack(anchor="w", padx=15, pady=(15, 10))

        self._mostrar_barra_predeterminados()

        lista_frame = ctk.CTkScrollableFrame(self.preview_frame, height=280, fg_color=styles.COLOR_BG_LIGHT)
        lista_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.playlist_filas = []
        for info_video in self.playlist_videos:
            self.playlist_filas.append(self._crear_fila_playlist(lista_frame, info_video))

        self._mostrar_selector_ruta()
        self._mostrar_boton_descarga_playlist()

    @staticmethod
    def _tipo_interno(valor_segmentado: str) -> str:
        """Convierte el texto del CTkSegmentedButton ('Audio'/'Video') al
        valor interno que usa core.youtube ('audio'/'video')."""
        return "audio" if valor_segmentado == "Audio" else "video"

    def _mostrar_barra_predeterminados(self):
        """Barra superior: elige Tipo/Formato/Calidad UNA vez y los aplica
        a todas las filas de la lista con un solo click, para no tener que
        configurar cada video a mano si todos van a quedar igual."""
        marco = ctk.CTkFrame(self.preview_frame, fg_color=styles.COLOR_BG_LIGHT, corner_radius=8)
        marco.pack(fill="x", padx=15, pady=(0, 10))
        interior = ctk.CTkFrame(marco, fg_color="transparent")
        interior.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(interior, text="Aplica a todas las pistas:", text_color=styles.COLOR_TEXT_SECONDARY,
                     font=styles.FONT_LABEL_SMALL).pack(side="left", padx=(0, 10))

        self.pred_tipo = ctk.CTkSegmentedButton(
            interior, values=["Audio", "Video"], width=120, height=30,
            fg_color=styles.COLOR_BORDER, selected_color=styles.COLOR_BORDER_ALT,
            unselected_color=styles.COLOR_BORDER, text_color=styles.COLOR_TEXT_MAIN,
            command=self._cambiar_tipo_predeterminado,
        )
        self.pred_tipo.set("Video")
        self.pred_tipo.pack(side="left", padx=(0, 6))

        self.pred_formato = ctk.CTkComboBox(interior, values=youtube.FORMATOS_VIDEO, width=90,
                                             fg_color=styles.COLOR_BG_WHITE, text_color=styles.COLOR_TEXT_MAIN)
        self.pred_formato.set(youtube.FORMATOS_VIDEO[0])
        self.pred_formato.pack(side="left", padx=(0, 6))

        self.pred_calidad = ctk.CTkComboBox(
            interior, values=["Mejor disponible", "Calidad media", "Más liviano"], width=140,
            fg_color=styles.COLOR_BG_WHITE, text_color=styles.COLOR_TEXT_MAIN,
        )
        self.pred_calidad.set("Mejor disponible")
        self.pred_calidad.pack(side="left", padx=(0, 6))

        ctk.CTkButton(interior, text="Aplicar a todos", command=self._aplicar_predeterminados_a_todos,
                      fg_color=styles.COLOR_PRIMARY, hover_color=styles.COLOR_PRIMARY_HOVER,
                      width=130, height=30).pack(side="left", padx=(6, 0))

    def _cambiar_tipo_predeterminado(self, valor):
        tipo = self._tipo_interno(valor)
        opciones_formato = youtube.FORMATOS_AUDIO if tipo == "audio" else youtube.FORMATOS_VIDEO
        self.pred_formato.configure(values=opciones_formato)
        self.pred_formato.set(opciones_formato[0])

    def _aplicar_predeterminados_a_todos(self):
        tipo = self._tipo_interno(self.pred_tipo.get())
        formato = self.pred_formato.get()
        nivel = self.pred_calidad.get()
        indice_por_nivel = {
            "Mejor disponible": lambda n: 0,
            "Calidad media": lambda n: n // 2,
            "Más liviano": lambda n: n - 1,
        }

        for fila in self.playlist_filas:
            fila["seg_tipo"].set("Audio" if tipo == "audio" else "Video")
            opciones_formato = youtube.FORMATOS_AUDIO if tipo == "audio" else youtube.FORMATOS_VIDEO
            fila["formato_combo"].configure(values=opciones_formato)
            fila["formato_combo"].set(formato if formato in opciones_formato else opciones_formato[0])
            self._recalcular_fila_playlist(fila)

            labels = list(fila["mapa_calidad"].keys())
            indice = min(indice_por_nivel.get(nivel, lambda n: 0)(len(labels)), len(labels) - 1)
            fila["calidad_combo"].set(labels[indice])

        self._al_cambiar_seleccion_playlist()

    def _crear_fila_playlist(self, lista_frame, info_video):
        fila_widget = ctk.CTkFrame(lista_frame, fg_color="transparent")
        fila_widget.pack(fill="x", pady=4)

        fila = {"info": info_video}

        var_incluir = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(fila_widget, text="", variable=var_incluir, width=20,
                         command=self._al_cambiar_seleccion_playlist).pack(side="left", padx=(0, 6))
        fila["incluir"] = var_incluir

        titulo = info_video.get("title", "Sin título")
        if len(titulo) > 26:
            titulo = titulo[:26] + "..."
        ctk.CTkLabel(fila_widget, text=titulo, text_color=styles.COLOR_TEXT_MAIN, anchor="w",
                     width=170, wraplength=170, justify="left").pack(side="left", padx=(0, 6))

        seg_tipo = ctk.CTkSegmentedButton(
            fila_widget, values=["Audio", "Video"], width=110, height=28,
            fg_color=styles.COLOR_BORDER, selected_color=styles.COLOR_BORDER_ALT,
            unselected_color=styles.COLOR_BORDER, text_color=styles.COLOR_TEXT_MAIN,
            command=lambda _, f=fila: self._al_cambiar_tipo_fila(f),
        )
        seg_tipo.set("Video")
        seg_tipo.pack(side="left", padx=(0, 6))
        fila["seg_tipo"] = seg_tipo

        formato_combo = ctk.CTkComboBox(
            fila_widget, values=youtube.FORMATOS_VIDEO, width=85,
            fg_color=styles.COLOR_BG_WHITE, text_color=styles.COLOR_TEXT_MAIN,
            command=lambda _, f=fila: self._recalcular_fila_playlist(f),
        )
        formato_combo.set(youtube.FORMATOS_VIDEO[0])
        formato_combo.pack(side="left", padx=(0, 6))
        fila["formato_combo"] = formato_combo

        calidad_combo = ctk.CTkComboBox(
            fila_widget, values=["Cargando..."], width=140,
            fg_color=styles.COLOR_BG_WHITE, text_color=styles.COLOR_TEXT_MAIN,
            command=lambda _: self._al_cambiar_seleccion_playlist(),
        )
        calidad_combo.pack(side="left")
        fila["calidad_combo"] = calidad_combo

        self._recalcular_fila_playlist(fila)
        return fila

    def _al_cambiar_tipo_fila(self, fila):
        """Se llama cuando cambia el SegmentedButton Audio/Video de UNA
        fila: hay que refrescar sus opciones de Formato (son distintas
        para audio y video) antes de recalcular la calidad."""
        tipo = self._tipo_interno(fila["seg_tipo"].get())
        opciones_formato = youtube.FORMATOS_AUDIO if tipo == "audio" else youtube.FORMATOS_VIDEO
        fila["formato_combo"].configure(values=opciones_formato)
        fila["formato_combo"].set(opciones_formato[0])
        self._recalcular_fila_playlist(fila)

    def _recalcular_fila_playlist(self, fila):
        """Vuelve a calcular las opciones de Calidad de una fila, según su
        Tipo y Formato actuales, y refresca el total estimado."""
        tipo = self._tipo_interno(fila["seg_tipo"].get())
        formato = fila["formato_combo"].get()
        opciones = youtube.obtener_opciones_calidad(fila["info"], tipo, formato)

        fila["mapa_calidad"] = {op["label"]: op["valor"] for op in opciones}
        fila["mapa_tam"] = {op["label"]: op["tamaño_mb"] for op in opciones}
        labels = list(fila["mapa_calidad"].keys())
        fila["calidad_combo"].configure(values=labels, state=("disabled" if len(labels) == 1 else "normal"))
        fila["calidad_combo"].set(labels[0])
        self._al_cambiar_seleccion_playlist()

    def _al_cambiar_seleccion_playlist(self):
        """Se llama cada vez que cambia algo que afecta cuánto se va a
        descargar: marcar/desmarcar un video, o cambiar su tipo/formato/
        calidad. Actualiza el contador del botón y el tamaño total."""
        if not hasattr(self, "playlist_filas"):
            return

        if hasattr(self, "btn_descargar_playlist"):
            cantidad = sum(1 for f in self.playlist_filas if f["incluir"].get())
            self.btn_descargar_playlist.configure(text=f"Descargar seleccionados ({cantidad})")

        if hasattr(self, "playlist_total_label"):
            total_mb = 0.0
            for fila in self.playlist_filas:
                if not fila["incluir"].get():
                    continue
                total_mb += fila["mapa_tam"].get(fila["calidad_combo"].get(), 0)
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

        tareas = []
        for fila in seleccionados:
            tareas.append({
                "info": fila["info"],
                "tipo": self._tipo_interno(fila["seg_tipo"].get()),
                "formato": fila["formato_combo"].get(),
                "valor_calidad": fila["mapa_calidad"].get(fila["calidad_combo"].get()),
            })

        self.btn_descargar_playlist.pack_forget()
        self.playlist_progress_bar.set(0)
        self.playlist_progress_label.configure(text="Iniciando descarga...")
        self.playlist_progress_frame.pack(fill="x", padx=15, pady=(0, 20))
        self.status_label.configure(text="● Descargando...", text_color=styles.COLOR_PRIMARY)

        threading.Thread(target=self._hilo_descarga_playlist, args=(tareas,), daemon=True).start()

    def _hilo_descarga_playlist(self, tareas):
        total = len(tareas)
        fallidos = 0

        for i, tarea in enumerate(tareas, start=1):
            info_video = tarea["info"]
            tipo = tarea["tipo"]
            formato = tarea["formato"]
            titulo = info_video.get("title", "Sin título")
            self.after(0, lambda i=i, t=titulo: self.playlist_progress_label.configure(
                text=f"Video {i}/{total}: {t}"))
            self.after(0, lambda i=i: self.playlist_progress_bar.set((i - 1) / total))

            try:
                ruta_final = youtube.predecir_ruta_final(self.download_path, tipo, formato, info_video)
                opts = youtube.construir_opciones_descarga(
                    self.download_path, tipo, formato, tarea["valor_calidad"],
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

        tipo_frame = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        tipo_frame.pack(fill="x", padx=15, pady=5)
        self.seg_tipo = ctk.CTkSegmentedButton(
            tipo_frame, values=["Audio", "Video"], command=self._cambiar_tipo,
            dynamic_resizing=False, width=200, height=35,
            fg_color=styles.COLOR_BORDER, selected_color=styles.COLOR_BORDER_ALT,
            unselected_color=styles.COLOR_BORDER, text_color=styles.COLOR_TEXT_MAIN,
        )
        self.seg_tipo.set("Video")
        self.seg_tipo.pack(anchor="w")

        self.formato_frame = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        self.formato_frame.pack(fill="x", padx=15, pady=(10, 5))

        self.quality_frame = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        self.quality_frame.pack(fill="x", padx=15, pady=(10, 15))

        self._cambiar_tipo("Video")

    def _cambiar_tipo(self, valor):
        tipo = self._tipo_interno(valor)
        self.download_type.set(tipo)
        opciones_formato = youtube.FORMATOS_AUDIO if tipo == "audio" else youtube.FORMATOS_VIDEO
        self._construir_grid_formato(opciones_formato)
        self._cambiar_formato(opciones_formato[0])

    def _construir_grid_formato(self, opciones):
        for widget in self.formato_frame.winfo_children():
            widget.destroy()
        self._botones_formato = {}
        for nombre in opciones:
            btn = ctk.CTkButton(
                self.formato_frame, text=nombre, width=80, height=32,
                fg_color=styles.COLOR_BORDER_ALT, hover_color=styles.COLOR_HOVER_LIGHT,
                text_color=styles.COLOR_TEXT_MAIN,
                command=lambda n=nombre: self._cambiar_formato(n),
            )
            btn.pack(side="left", padx=(0, 8))
            self._botones_formato[nombre] = btn

    def _cambiar_formato(self, formato):
        self.formato_actual = formato
        for nombre, btn in self._botones_formato.items():
            if nombre == formato:
                btn.configure(fg_color=styles.COLOR_PRIMARY, text_color="white")
            else:
                btn.configure(fg_color=styles.COLOR_BORDER_ALT, text_color=styles.COLOR_TEXT_MAIN)
        self._actualizar_opciones_calidad()

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
        # Ya no descarga al toque: agrega el video (con su formato y
        # calidad elegidos) a la Cola de Descargas del panel derecho.
        # La descarga real pasa a ser en lote, desde ahí.
        self.btn_agregar_lista = ctk.CTkButton(
            self.preview_frame, text="➕ Añadir a la lista", command=self.agregar_a_cola,
            fg_color=styles.COLOR_PRIMARY, hover_color=styles.COLOR_PRIMARY_HOVER,
            font=styles.FONT_BUTTON, height=45,
        )
        self.btn_agregar_lista.pack(fill="x", padx=15, pady=20)

    # ------------------------------------------------------------------
    # Selección de tipo y calidad (usa core.youtube para calcular opciones)
    # ------------------------------------------------------------------

    def _actualizar_opciones_calidad(self):
        for widget in self.quality_frame.winfo_children():
            widget.destroy()

        tipo = self.download_type.get()
        opciones = youtube.obtener_opciones_calidad(self.current_video_info, tipo, self.formato_actual)
        etiqueta = "Calidad de video" if tipo == "video" else "Calidad de audio"
        ctk.CTkLabel(self.quality_frame, text=etiqueta, text_color=styles.COLOR_TEXT_SECONDARY).pack(anchor="w")

        self.quality_options_map = {op["label"]: op["valor"] for op in opciones}
        labels = list(self.quality_options_map.keys())

        if len(opciones) == 1:
            # Nada que elegir (M4A/OPUS nativos, o WAV sin pérdida): solo
            # un aviso informativo, sin dropdown.
            ctk.CTkLabel(self.quality_frame, text=f"🎼 {labels[0]}",
                         text_color=styles.COLOR_TEXT_MUTED).pack(anchor="w", pady=5)
            self.quality_dropdown = None
            return

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
    # Cola de Descargas (panel derecho): agregar, quitar, y descargar en lote
    # ------------------------------------------------------------------

    def agregar_a_cola(self):
        """Toma la selección actual (video + tipo + formato + calidad) y
        la guarda en la cola local, en vez de descargar de inmediato."""
        if not self.current_video_info:
            return

        tipo = self.download_type.get()
        formato = self.formato_actual
        valor_calidad = None
        if self.quality_dropdown is not None:
            valor_calidad = self.quality_options_map.get(self.quality_dropdown.get())

        self.cola_descargas.append({
            "info": self.current_video_info,
            "tipo": tipo,
            "formato": formato,
            "valor_calidad": valor_calidad,
            "titulo": self.current_video_info.get("title", "Sin título"),
        })
        self._refrescar_cola()
        self.reiniciar_formulario()

    def _refrescar_cola(self):
        for widget in self.cola_frame.winfo_children():
            widget.destroy()

        if not self.cola_descargas:
            ctk.CTkLabel(self.cola_frame, text="Agrega videos desde la izquierda para armar tu lista.",
                         text_color=styles.COLOR_TEXT_MUTED, font=styles.FONT_LABEL_SMALL,
                         wraplength=250, justify="left").pack(fill="x", padx=10, pady=5)
        else:
            for indice, item in enumerate(self.cola_descargas):
                self._crear_item_cola(item, indice)

        self.btn_descargar_cola.configure(text=f"Descargar lista ({len(self.cola_descargas)})")

    def _crear_item_cola(self, item, indice):
        fila = ctk.CTkFrame(self.cola_frame, fg_color=styles.COLOR_BG_WHITE, corner_radius=8)
        fila.pack(fill="x", pady=4)
        contenido = ctk.CTkFrame(fila, fg_color="transparent")
        contenido.pack(fill="x", padx=10, pady=6)

        icono = "🎵" if item["tipo"] == "audio" else "🎬"
        titulo = item["titulo"]
        if len(titulo) > 26:
            titulo = titulo[:26] + "..."
        ctk.CTkLabel(contenido, text=f"{icono} {titulo}", text_color=styles.COLOR_TEXT_MAIN,
                     font=styles.FONT_LABEL_SMALL, anchor="w").pack(side="left", fill="x", expand=True)

        ctk.CTkButton(contenido, text="✕", width=24, height=24, fg_color="transparent",
                      text_color=styles.COLOR_TEXT_MUTED, hover_color=styles.COLOR_HOVER_LIGHT,
                      command=lambda i=indice: self._quitar_de_cola(i)).pack(side="right")

    def _quitar_de_cola(self, indice):
        del self.cola_descargas[indice]
        self._refrescar_cola()

    def iniciar_descarga_cola(self):
        if not self.cola_descargas:
            dialogs.mostrar_advertencia(self, "Lista vacía",
                                         "Agrega al menos un video a la lista antes de descargar.")
            return

        if not youtube.ffmpeg_disponible():
            dialogs.mostrar_error(
                self, "Falta un componente",
                "No se encontró ffmpeg. Reinstala ClipSave con la versión más reciente "
                "del instalador, que ya lo incluye.",
            )
            return

        nombre_carpeta = ctk.CTkInputDialog(
            text="¿Cómo quieres llamar a esta carpeta/playlist?", title="Nombre de la lista",
        ).get_input()
        if not nombre_carpeta:
            return  # Canceló el diálogo

        tareas = list(self.cola_descargas)  # copia: la cola visible se limpia al terminar
        self.btn_descargar_cola.configure(state="disabled")
        self.cola_progress_bar.set(0)
        self.cola_progress_label.configure(text="Iniciando descarga...")
        self.cola_progress_frame.pack(fill="x", padx=20, pady=(0, 10))
        self.status_label.configure(text="● Descargando...", text_color=styles.COLOR_PRIMARY)

        threading.Thread(target=self._hilo_descarga_cola, args=(tareas, nombre_carpeta), daemon=True).start()

    def _hilo_descarga_cola(self, tareas, nombre_carpeta):
        total = len(tareas)
        fallidos = 0

        for i, tarea in enumerate(tareas, start=1):
            titulo = tarea["titulo"]
            self.after(0, lambda i=i, t=titulo: self.cola_progress_label.configure(text=f"{i}/{total}: {t}"))
            self.after(0, lambda i=i: self.cola_progress_bar.set((i - 1) / total))

            try:
                opts = youtube.construir_opciones_descarga(
                    self.download_path, tarea["tipo"], tarea["formato"], tarea["valor_calidad"],
                    progress_hook=self._progress_hook_cola(i, total), nombre_carpeta=nombre_carpeta,
                )
                ruta_final = youtube.predecir_ruta_final(
                    self.download_path, tarea["tipo"], tarea["formato"], tarea["info"],
                    nombre_carpeta=nombre_carpeta,
                )
                youtube.descargar(tarea["info"]["webpage_url"], opts)
                historial.agregar_entrada(titulo, tarea["tipo"], ruta_final)
            except Exception:
                fallidos += 1  # Un video privado/borrado/con error no tumba el resto de la lista

        self.after(0, self._finalizar_descarga_cola, fallidos, total, nombre_carpeta)

    def _progress_hook_cola(self, indice, total):
        def hook(d):
            if d["status"] == "downloading":
                try:
                    descargado = d.get("downloaded_bytes") or 0
                    total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    progreso_item = (descargado / total_bytes) if total_bytes else 0
                    progreso_global = ((indice - 1) + progreso_item) / total
                    self.after(0, lambda p=progreso_global: self.cola_progress_bar.set(p))
                except Exception:
                    pass
        return hook

    def _finalizar_descarga_cola(self, fallidos, total, nombre_carpeta):
        self.cola_progress_frame.pack_forget()
        self.btn_descargar_cola.configure(state="normal")
        self.status_label.configure(text="● Listo", text_color=styles.COLOR_SUCCESS)

        self.cola_descargas.clear()
        self._refrescar_cola()
        self._refrescar_historial()

        try:
            abrir_carpeta(os.path.join(self.download_path, nombre_carpeta))
        except Exception:
            pass

        if fallidos:
            dialogs.mostrar_advertencia(
                self, "Descarga completada con avisos",
                f"{fallidos} de {total} elementos no se pudieron descargar "
                "(posiblemente privados, eliminados o restringidos).",
            )

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