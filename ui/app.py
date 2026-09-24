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
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from core import thumbnails, updater, youtube
from core.resources import resource_path
from core.utils import format_duration, truncate_path
from core.version import APP_VERSION
from ui import styles

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("dark-blue")


class ClipSaveApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ClipSave - Descargador de YouTube")
        self.geometry(styles.WINDOW_SIZE)
        self.resizable(False, False)

        self._configurar_icono()

        # Estado
        self.download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.current_video_info = None
        self.download_type = tk.StringVar(value="video")
        self.quality_options_map = {}  # label -> valor (height o bitrate)

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

        ctk.CTkLabel(self.header_frame, text="ClipSave", text_color=styles.COLOR_PRIMARY,
                     font=styles.FONT_LOGO).pack(side="left", padx=(30, 10), pady=15)
        ctk.CTkLabel(self.header_frame, text=APP_VERSION, text_color="#A6ACAF",
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

        self.btn_analizar = ctk.CTkButton(self.search_frame, text="Analizar", command=self.analizar_url,
                                           fg_color=styles.COLOR_DARK, hover_color=styles.COLOR_DARK_HOVER,
                                           width=100, height=35)
        self.btn_analizar.pack(side="right", padx=10, pady=5)

        self.preview_frame = ctk.CTkFrame(self.main_content, fg_color=styles.COLOR_BG_WHITE, corner_radius=12,
                                           border_width=1, border_color=styles.COLOR_BORDER)

    def _construir_panel_descargas(self):
        self.recent_frame = ctk.CTkFrame(self, width=styles.RECENT_PANEL_WIDTH, corner_radius=0,
                                          fg_color=styles.COLOR_BG_LIGHT, border_width=1, border_color=styles.COLOR_BORDER)
        self.recent_frame.grid(row=1, column=1, sticky="nsew")
        self.recent_frame.grid_propagate(False)

        ctk.CTkLabel(self.recent_frame, text="Descarga actual", font=styles.FONT_SECTION,
                     text_color=styles.COLOR_TEXT_MAIN).pack(anchor="w", padx=20, pady=(20, 10))

        self.progress_bar = ctk.CTkProgressBar(self.recent_frame, progress_color=styles.COLOR_PRIMARY,
                                                fg_color=styles.COLOR_BORDER_ALT)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=5)

        self.progress_text = ctk.CTkLabel(self.recent_frame, text="Esperando enlace...",
                                           text_color=styles.COLOR_TEXT_MUTED, font=styles.FONT_LABEL_SMALL,
                                           wraplength=310, justify="left")
        self.progress_text.pack(anchor="w", padx=20, pady=5)

    # ------------------------------------------------------------------
    # Análisis de URL (dispara lógica en core.youtube)
    # ------------------------------------------------------------------

    def analizar_url(self):
        url = self.url_entry.get()
        if not url:
            messagebox.showwarning("Error", "Por favor, pega una URL de YouTube.")
            return

        self.status_label.configure(text="● Analizando...", text_color=styles.COLOR_WARNING)
        self.btn_analizar.configure(state="disabled", text="...")

        threading.Thread(target=self._hilo_analizar, args=(url,), daemon=True).start()

    def _hilo_analizar(self, url):
        try:
            info = youtube.analizar_url(url)
            self.after(0, self._mostrar_previsualizacion, info)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"No se pudo analizar la URL:\n{str(e)}"))
            self.after(0, self._resetear_busqueda)

    def _resetear_busqueda(self):
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
            format_frame, values=["Video (MP4)", "Audio (MP3)"], command=self._cambiar_tipo_descarga,
            dynamic_resizing=False, width=300, height=35,
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
            self.preview_frame, text="⬇️ Descargar ahora", command=self.iniciar_descarga,
            fg_color=styles.COLOR_PRIMARY, hover_color=styles.COLOR_PRIMARY_HOVER,
            font=styles.FONT_BUTTON, height=45,
        )
        self.btn_descargar_ya.pack(fill="x", padx=15, pady=20)

    # ------------------------------------------------------------------
    # Selección de tipo y calidad (usa core.youtube para calcular opciones)
    # ------------------------------------------------------------------

    def _cambiar_tipo_descarga(self, value):
        if "Video" in value:
            self.download_type.set("video")
            self._actualizar_opciones_calidad("video")
        else:
            self.download_type.set("mp3")
            self._actualizar_opciones_calidad("mp3")

    def _actualizar_opciones_calidad(self, tipo):
        for widget in self.quality_frame.winfo_children():
            widget.destroy()

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
            messagebox.showerror(
                "Falta un componente",
                "No se encontró ffmpeg. Reinstala ClipSave con la versión más reciente "
                "del instalador, que ya lo incluye.",
            )
            return

        self.btn_descargar_ya.configure(state="disabled", text="Descargando...")
        self.status_label.configure(text="● Descargando...", text_color=styles.COLOR_PRIMARY)

        url = self.current_video_info["webpage_url"]
        tipo = self.download_type.get()
        label_calidad = self.quality_dropdown.get()
        valor_calidad = self.quality_options_map.get(label_calidad)

        opts = youtube.construir_opciones_descarga(
            self.download_path, tipo, valor_calidad, progress_hook=self._progress_hook,
        )

        threading.Thread(target=self._hilo_descarga, args=(url, opts), daemon=True).start()

    def _hilo_descarga(self, url, opts):
        try:
            youtube.descargar(url, opts)
            self.after(0, lambda: messagebox.showinfo("Éxito", "Descarga completada correctamente."))
        except Exception as e:
            mensaje_error = str(e)
            self.after(0, lambda m=mensaje_error: messagebox.showerror("Error", f"Hubo un problema:\n{m}"))
        finally:
            self.after(0, self._finalizar_estado_descarga)

    def _finalizar_estado_descarga(self):
        self.btn_descargar_ya.configure(state="normal", text="⬇️ Descargar ahora")
        self.status_label.configure(text="● Listo", text_color=styles.COLOR_SUCCESS)
        self.progress_bar.set(0)
        self.progress_text.configure(text="Descarga finalizada.")

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
