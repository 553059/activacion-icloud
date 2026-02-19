# main.py
import threading
import queue
import time
import os
import socket
import webbrowser
import urllib.parse
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
import customtkinter as ctk
import backend_modules as backend

APP_POLL_INTERVAL_MS = 2000

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class JarvisApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("JARVIS ULTIMATE TOOL v1.0 — JARVIS ING")
        self.geometry("1100x720")
        self.grid_columnconfigure(1, weight=1)
        self.log_queue = queue.Queue()
        self.current_udid = None
        # in-memory log history for filtering/export (stores raw strings and structured tuples)
        self.log_history = []
        # display settings (truncation, colorize)
        self.max_value_length = 1000
        self.max_list_item_length = 300
        self.snippet_length = 800
        self.colorize_logs = True
        # filter state (defaults: show all)
        self.filter_levels = {"INFO": True, "WARN": True, "ERROR": True}
        self.filter_categories = {"DEVICE": True, "OWNER": True, "PANICS": True, "SERVER": True, "OTHER": True}

        # Sidebar
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self._add_sidebar_buttons(sidebar)

        # Main area
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.frames = {}
        self._build_frames()

        # Bottom console / logs
        console_frame = ctk.CTkFrame(self, height=180)
        console_frame.grid(row=1, column=1, sticky="nsew", padx=12, pady=(0,12))
        self._build_console(console_frame)

        # Start polling devices and log queue processor
        self.after(500, self.poll_device)
        self.after(100, self._process_log_queue)
        # refresh server signing status shortly after startup
        try:
            self.after(1500, self.refresh_server_signing_status)
        except Exception:
            pass

    def _add_sidebar_buttons(self, parent):
        ctk.CTkLabel(parent, text="JARVIS ING", font=ctk.CTkFont(size=18, weight="bold"), text_color="#00E6E6").pack(pady=(18,8))
        nav = [
            ("Inicio", self.show_dashboard),
            ("Launcher", lambda: self.show_frame("launcher")),
            ("Diagnóstico", lambda: self.show_frame("diagnostic")),
            ("Pánicos", lambda: self.show_frame("panics")),
            ("Servidor", lambda: self.show_frame("server")),
            ("Ajustes", lambda: self.show_frame("settings")),
        ]
        for txt, cmd in nav:
            ctk.CTkButton(parent, text=txt, width=200, fg_color="#08303A", hover_color="#005B5B", command=cmd).pack(pady=6)

    def _build_frames(self):
        # Dashboard frame
        f = ctk.CTkFrame(self.main_frame)
        f.grid(row=0, column=0, sticky="nsew")
        self.frames["dashboard"] = f
        self._populate_dashboard(f)

        # Launcher (accesos rápidos)
        f_launcher = ctk.CTkFrame(self.main_frame)
        self.frames["launcher"] = f_launcher
        self._populate_launcher(f_launcher)

        # Diagnostic / Owner Intel
        f2 = ctk.CTkFrame(self.main_frame)
        self.frames["diagnostic"] = f2
        self._populate_diagnostic(f2)
    def _populate_launcher(self, parent):
        ctk.CTkLabel(parent, text="Launcher — Accesos rápidos iPhone", font=ctk.CTkFont(size=16, weight="bold"), text_color="#00E6E6").pack(anchor="nw", padx=12, pady=8)
        ctk.CTkLabel(parent, text="Accesos útiles para configuración y diagnóstico de iPhone conectado:", font=ctk.CTkFont(size=12)).pack(anchor="nw", padx=12, pady=(0,8))

        # Botón para mostrar instrucciones de Wi-Fi/DNS
        ctk.CTkButton(parent, text="Instrucciones Wi-Fi / DNS Bypass", fg_color="#008080", width=260, command=self.show_dns_instructions).pack(padx=12, pady=8)

        # Botón para reiniciar SpringBoard
        ctk.CTkButton(parent, text="Reiniciar SpringBoard", fg_color="#005B5B", width=260, command=self.restart_springboard).pack(padx=12, pady=8)

        # Botón para abrir panel de información del dispositivo
        ctk.CTkButton(parent, text="Ver información del dispositivo", fg_color="#0066CC", width=260, command=self.show_dashboard).pack(padx=12, pady=8)

        # Botón para comprobar estado de activación (Activation Lock / ActivationState)
        ctk.CTkButton(parent, text="Comprobar estado de activación", fg_color="#FF8C00", width=260, command=self.check_activation_status).pack(padx=12, pady=8)

        # Botón para abrir el portal cautivo en el navegador y copiar URL / mostrar QR
        ctk.CTkButton(parent, text="Abrir portal / Mostrar QR", fg_color="#007ACC", width=260, command=self.open_captive_portal).pack(padx=12, pady=8)

        # Botón para generar Recovery Kit (PDF) desde la app
        ctk.CTkButton(parent, text="Generar Recovery PDF", fg_color="#7046FF", width=260, command=self.generate_recovery_pdf).pack(padx=12, pady=8)

        # Toggle: Firmar perfiles server-side
        self.server_signing_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(parent, text="Firmar perfiles (server-side)", variable=self.server_signing_var, command=self.toggle_server_profile_signing).pack(padx=12, pady=(6,8))

        # Botón para habilitar HTTPS en el portal (regenerar certificados + reload)
        ctk.CTkButton(parent, text="Habilitar HTTPS (portal)", fg_color="#208020", width=260, command=self.enable_https_on_portal).pack(padx=12, pady=8)

        # Botón para descargar certificado del portal y guía de instalación
        ctk.CTkButton(parent, text="Descargar certificado / Guía", fg_color="#0066CC", width=260, command=self.show_install_guide).pack(padx=12, pady=8)

        # Botón para intentar crear un hotspot Windows y forzar captive (requiere admin)
        ctk.CTkButton(parent, text="Forzar Captive (Hotspot)", fg_color="#CC3300", width=260, command=self.toggle_hotspot).pack(padx=12, pady=8)

        # Instrucciones visuales
        txt = (
            "\n\u2022 Para acceder a Configuración Wi-Fi en el iPhone: Ajustes > Wi-Fi > (i) en la red\n"
            "\u2022 Para cambiar DNS: Configuración Wi-Fi > (i) > Configurar DNS > Manual\n"
            "\u2022 Si necesitas más ayuda, consulta la pestaña Diagnóstico o Dashboard.\n"
        )
        ctk.CTkLabel(parent, text=txt, font=ctk.CTkFont(size=11), justify="left").pack(anchor="nw", padx=16, pady=(12,4))

        # Panics
        f3 = ctk.CTkFrame(self.main_frame)
        self.frames["panics"] = f3
        self._populate_panics(f3)

        # Server Interceptor
        f4 = ctk.CTkFrame(self.main_frame)
        self.frames["server"] = f4
        self._populate_server(f4)

        # Settings
        f5 = ctk.CTkFrame(self.main_frame)
        self.frames["settings"] = f5
        ctk.CTkLabel(f5, text="Ajustes", font=ctk.CTkFont(size=16, weight="bold")).pack(padx=20, pady=(12,6))
        ctk.CTkButton(f5, text="Exportar logs", fg_color="#0066CC", width=220, command=self.export_logs).pack(pady=8)
        ctk.CTkButton(f5, text="Abrir carpeta de logs", fg_color="#005B5B", width=220, command=self.open_logs_folder).pack(pady=8)
        ctk.CTkLabel(f5, text="Logs exportados a `logs/` (automático)").pack(padx=20, pady=(8,6))

        # Console display settings
        ctk.CTkLabel(f5, text="Consola — Opciones de visualización", font=ctk.CTkFont(size=12, weight="bold")).pack(padx=20, pady=(12,6))
        self.colorize_var = tk.BooleanVar(value=self.colorize_logs)
        ctk.CTkCheckBox(f5, text="Colorize logs", variable=self.colorize_var, command=self._on_toggle_colorize).pack(padx=20, pady=(0,8))

        # Truncation slider for large values
        self.max_value_length_var = tk.IntVar(value=self.max_value_length)
        ctk.CTkLabel(f5, text="Max length for displayed values (chars)").pack(padx=20, anchor="w")
        slider = ctk.CTkSlider(f5, from_=100, to=5000, number_of_steps=49, command=self._on_change_max_value_length)
        slider.set(self.max_value_length)
        slider.pack(padx=20, pady=(2,12))
        self._max_value_label = ctk.CTkLabel(f5, text=f"Current: {self.max_value_length}")
        self._max_value_label.pack(padx=20, pady=(0,12))


        self.show_dashboard()

    def show_frame(self, name):
        for frm in self.frames.values():
            frm.grid_forget()
        self.frames[name].grid(row=0, column=0, sticky="nsew")

    def show_dashboard(self):
        self.show_frame("dashboard")

    def _populate_dashboard(self, parent):
        left = ctk.CTkFrame(parent)
        left.pack(side="left", fill="y", padx=(12,8), pady=12)

        self.device_status_label = ctk.CTkLabel(left, text="Ningún dispositivo detectado", width=260, height=40, corner_radius=8)
        self.device_status_label.pack(padx=8, pady=8)

        self.device_info_text = ctk.CTkLabel(left, text="Esperando dispositivo...", justify="left")
        self.device_info_text.pack(padx=8, pady=6)

        # Utilities quick-actions
        ctk.CTkButton(left, text="Reiniciar SpringBoard", fg_color="#005B5B", command=self.restart_springboard).pack(pady=(18,4), padx=8)
        ctk.CTkButton(left, text="Bypass DNS HUD (instrucciones)", fg_color="#005B5B", command=self.show_dns_instructions).pack(pady=4, padx=8)

        # Owner intel quick
        ctk.CTkButton(left, text="Extraer Info Propietario", fg_color="#008080", command=self.extract_owner_intel).pack(pady=(30,4), padx=8)

        # Center / flexible area (info panels)
        right = ctk.CTkFrame(parent)
        right.pack(side="right", fill="both", expand=True, padx=(8,12), pady=12)
        ctk.CTkLabel(right, text="Módulo Dashboard — Auto-Detect", font=ctk.CTkFont(size=16, weight="bold"), text_color="#00E6E6").pack(anchor="nw", padx=10, pady=(6,12))
        self.dashboard_detail = ctk.CTkTextbox(right, width=720, height=420)
        self.dashboard_detail.pack(padx=12, pady=6)
        self.dashboard_detail.insert("0.0", "Salida de detección y consejos aparecerán aquí.")
        self.dashboard_detail.configure(state="disabled")

    def _populate_diagnostic(self, parent):
        ctk.CTkLabel(parent, text="Inteligencia (Owner Intel)", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="nw", padx=12, pady=8)
        btn = ctk.CTkButton(parent, text="Extraer Info Propietario", command=self.extract_owner_intel, width=240, fg_color="#00A2A2")
        btn.pack(padx=12, pady=12)
        self.owner_text = ctk.CTkTextbox(parent, height=360)
        self.owner_text.pack(fill="both", expand=True, padx=12, pady=8)
        self.owner_text.insert("0.0", "Resultados aparecerán aquí.")
        self.owner_text.configure(state="disabled")

    def _populate_panics(self, parent):
        ctk.CTkLabel(parent, text="Hardware Check (Panic Analyzer)", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="nw", padx=12, pady=8)
        ctk.CTkButton(parent, text="Analizar Pánicos", command=self.analyze_panics, fg_color="#FF6B6B", width=220).pack(padx=12, pady=10)
        self.panics_text = ctk.CTkTextbox(parent, height=420)
        self.panics_text.pack(fill="both", expand=True, padx=12, pady=8)
        self.panics_text.configure(state="disabled")

    def _populate_server(self, parent):
        ctk.CTkLabel(parent, text="Server Interceptor", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="nw", padx=12, pady=8)
        ctk.CTkButton(parent, text="Solicitar Ticket de Activación", command=self.request_activation_ticket, fg_color="#0066CC", width=280).pack(padx=12, pady=10)
        self.server_text = ctk.CTkTextbox(parent, height=420)
        self.server_text.pack(fill="both", expand=True, padx=12, pady=8)
        self.server_text.configure(state="disabled")

    def _build_console(self, parent):
        ctk.CTkLabel(parent, text="Consola — Logs en vivo", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=8, pady=(6,0))
        # Filters toolbar (levels + categories + text search)
        filter_frame = ctk.CTkFrame(parent, corner_radius=4)
        filter_frame.pack(fill="x", padx=8, pady=(4,6))

        # Level filters
        self.filter_info_var = tk.BooleanVar(value=True)
        self.filter_warn_var = tk.BooleanVar(value=True)
        self.filter_error_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(filter_frame, text="INFO", variable=self.filter_info_var, command=self.update_log_view).pack(side="left", padx=(8,4))
        ctk.CTkCheckBox(filter_frame, text="WARN", variable=self.filter_warn_var, command=self.update_log_view).pack(side="left", padx=4)
        ctk.CTkCheckBox(filter_frame, text="ERROR", variable=self.filter_error_var, command=self.update_log_view).pack(side="left", padx=4)

        # Category filters
        self.filter_device_var = tk.BooleanVar(value=True)
        self.filter_owner_var = tk.BooleanVar(value=True)
        self.filter_panics_var = tk.BooleanVar(value=True)
        self.filter_server_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(filter_frame, text="DEVICE", variable=self.filter_device_var, command=self.update_log_view).pack(side="left", padx=(16,4))
        ctk.CTkCheckBox(filter_frame, text="OWNER", variable=self.filter_owner_var, command=self.update_log_view).pack(side="left", padx=4)
        ctk.CTkCheckBox(filter_frame, text="PANICS", variable=self.filter_panics_var, command=self.update_log_view).pack(side="left", padx=4)
        ctk.CTkCheckBox(filter_frame, text="SERVER", variable=self.filter_server_var, command=self.update_log_view).pack(side="left", padx=4)

        # Quick search
        self.filter_text_var = tk.StringVar(value="")
        search = ctk.CTkEntry(filter_frame, placeholder_text="Buscar en logs...", width=220, textvariable=self.filter_text_var)
        search.pack(side="right", padx=8)
        search.bind("<KeyRelease>", lambda e: self.update_log_view())

        # Console area
        self.console = scrolledtext.ScrolledText(parent, bg="#071923", fg="#E6FFFF", insertbackground="#E6FFFF", height=12)
        self.console.pack(fill="both", expand=True, padx=8, pady=8)
        self.console.configure(state="disabled", font=("Consolas", 10))
        # Text tags for structured & colorized logs
        self.console.tag_config("header", foreground="#00E6E6", font=("Consolas", 10, "bold"))
        self.console.tag_config("info", foreground="#E6FFFF")
        self.console.tag_config("warning", foreground="#FFB86B")
        self.console.tag_config("error", foreground="#FF6B6B")
        self.console.tag_config("key", foreground="#9ED6FF")
        self.console.tag_config("value", foreground="#FFFFFF")
        self.console.tag_config("section", foreground="#00A2A2", underline=1)

    # ---- Actions / background tasks ----
    def poll_device(self):
        def worker():
            try:
                devices = backend.list_devices()
                if devices:
                    udid = devices[0]
                    info = backend.get_device_info(udid)
                    self.log(f"Dispositivo detectado: {udid}")
                    self.current_udid = udid
                    # structured device info for console
                    try:
                        self.log_structured("Device detected", {
                            "udid": info.get("udid"),
                            "model": info.get("model"),
                            "serial": info.get("serial"),
                            "imei": info.get("imei"),
                            "ios_version": info.get("ios_version")
                        }, level="INFO", category="DEVICE")
                    except Exception:
                        pass
                    self.after(0, lambda: self._update_device_ui(info))
                else:
                    self.current_udid = None
                    self.after(0, lambda: self._clear_device_ui())
            except Exception as e:
                self.log(f"[ERROR] Poll device: {e}")
        threading.Thread(target=worker, daemon=True).start()
        self.after(APP_POLL_INTERVAL_MS, self.poll_device)

    def _update_device_ui(self, info: dict):
        # status color by IMEI presence
        imei = info.get("imei")
        status = "OK" if imei else "BASEBAND / SIN IMEI"
        color = "#0CB400" if imei else "#D12B2B"
        self.device_status_label.configure(text=f"{status} — {info.get('model','?')}", fg_color=color)
        txt = (
            f"Modelo: {info.get('model')}\n"
            f"UDID: {info.get('udid')}\n"
            f"Serie: {info.get('serial')}\n"
            f"IMEI: {info.get('imei') or '—'}\n"
            f"iOS: {info.get('ios_version')}\n"
            f"Batería: {info.get('battery_percent') or '—'}%  •  Ciclos: {info.get('battery_cycles') or '—'}\n"
        )
        self.device_info_text.configure(text=txt)
        self.dashboard_detail.configure(state="normal")
        self.dashboard_detail.delete("0.0", "end")
        self.dashboard_detail.insert("0.0", "Última lectura:\n\n" + txt)
        self.dashboard_detail.configure(state="disabled")

    def _clear_device_ui(self):
        self.device_status_label.configure(text="Ningún dispositivo detectado", fg_color=None)
        self.device_info_text.configure(text="Esperando dispositivo...")
        self.dashboard_detail.configure(state="normal")
        self.dashboard_detail.delete("0.0", "end")
        self.dashboard_detail.insert("0.0", "Ningún dispositivo conectado.")
        self.dashboard_detail.configure(state="disabled")

    def extract_owner_intel(self):
        udid = self.current_udid
        if not udid:
            messagebox.showwarning("No device", "Conecta un dispositivo por USB primero.")
            return

        def task():
            self.log("Ejecutando extracción de info propietario...")
            try:
                res = backend.extract_owner_info(udid)
                out = f"Email: {res.get('email_masked') or '—'}\nPhone: {res.get('phone_masked') or '—'}\n\nRAW:\n{res.get('raw')[:2000]}"
                self.after(0, lambda: self._set_owner_text(out))
                self.log("Extracción completada.")
                # structured owner info in console
                try:
                    self.log_structured("Owner info", {
                        "email_masked": res.get("email_masked"),
                        "phone_masked": res.get("phone_masked"),
                        "raw_snippet": (res.get("raw") or "")[:800]
                    }, level="INFO", category="OWNER")
                except Exception:
                    pass
            except Exception as e:
                self.log(f"[ERROR] extract_owner_intel: {e}")
        threading.Thread(target=task, daemon=True).start()

    def _set_owner_text(self, text):
        self.owner_text.configure(state="normal")
        self.owner_text.delete("0.0", "end")
        self.owner_text.insert("0.0", text)
        self.owner_text.configure(state="disabled")

    def analyze_panics(self):
        udid = self.current_udid
        if not udid:
            messagebox.showwarning("No device", "Conecta un dispositivo por USB primero.")
            return

        def task():
            self.log("Descargando y analizando pánicos (ips)... esto puede tardar unos segundos.")
            try:
                res = backend.analyze_panics(udid)
                summary = f"Archivos analizados: {len(res['files'])}\nHallazgos: {res['matches']}\nDiagnóstico sugerido: {res['diagnosis']}\n\nDetalles (primeros 2000 chars):\n{res.get('snippets','')[:2000]}"
                self.after(0, lambda: self._set_panics_text(summary))
                self.log("Análisis de pánicos completado.")
                # structured panics summary
                try:
                    self.log_structured("Panic analysis", {
                        "files_analyzed": len(res.get("files", [])),
                        "matches": res.get("matches"),
                        "diagnosis": res.get("diagnosis")
                    }, level=("WARN" if res.get("matches") else "INFO"), category="PANICS")
                except Exception:
                    pass
            except Exception as e:
                self.log(f"[ERROR] analyze_panics: {e}")
        threading.Thread(target=task, daemon=True).start()

    def _set_panics_text(self, text):
        self.panics_text.configure(state="normal")
        self.panics_text.delete("0.0", "end")
        self.panics_text.insert("0.0", text)
        self.panics_text.configure(state="disabled")

    def log_structured(self, title: str, data, level: str = "INFO", category: str = ""):
        """Enqueue a structured log entry (thread-safe) and save to history."""
        ts = time.strftime("%H:%M:%S")
        entry = ("STRUCT", ts, title, level.upper(), (category or "").upper(), data)
        # keep history for filtering/export
        try:
            self.log_history.append(entry)
        except Exception:
            pass
        self.log_queue.put(entry)

    def _insert_structured_log(self, ts: str, title: str, level: str, category: str, data):
        """Insert formatted structured data into the console (must be called on main thread)."""
        # header
        header = f"[{ts}] [{level}] [{category}] {title}\n"
        if self.colorize_logs:
            htag = "header" if level == "INFO" else ("warning" if level.startswith("W") else "error" if level == "ERROR" else "info")
        else:
            htag = "info"
        self.console.insert("end", header, htag)
        # body (dict/list/primitive)
        def insert_kv(k, v, indent=2):
            pad = " " * indent
            if isinstance(v, dict):
                self.console.insert("end", f"{pad}{k}:\n", ("key",) if self.colorize_logs else ())
                for kk, vv in v.items():
                    insert_kv(kk, vv, indent + 2)
            elif isinstance(v, list):
                self.console.insert("end", f"{pad}{k}: [\n", ("key",) if self.colorize_logs else ())
                for item in v:
                    if isinstance(item, (dict, list)):
                        insert_kv("-", item, indent + 2)
                    else:
                        val = str(item)
                        if len(val) > self.max_list_item_length:
                            val = val[:self.max_list_item_length] + "..."
                        if self.colorize_logs:
                            self.console.insert("end", f"{pad}  - ", ("key",))
                            self.console.insert("end", val + "\n", ("value",))
                        else:
                            self.console.insert("end", f"{pad}  - {val}\n")
                self.console.insert("end", f"{pad}]\n")
            else:
                val = str(v) if v is not None else "—"
                if len(val) > self.max_value_length:
                    val = val[:self.max_value_length] + "..."
                if self.colorize_logs:
                    self.console.insert("end", f"{pad}{k}: ", ("key",))
                    self.console.insert("end", val + "\n", ("value",))
                else:
                    self.console.insert("end", f"{pad}{k}: {val}\n")
        # if primitive, just print
        if isinstance(data, dict):
            for k, v in data.items():
                insert_kv(k, v)
        else:
            s = str(data)
            if len(s) > self.snippet_length:
                s = s[:self.snippet_length] + "..."
            if self.colorize_logs:
                self.console.insert("end", s + "\n", ("value",))
            else:
                self.console.insert("end", s + "\n")
        self.console.insert("end", "\n")


    def request_activation_ticket(self):
        udid = self.current_udid
        if not udid:
            messagebox.showwarning("No device", "Conecta un dispositivo por USB primero.")
            return

        def task():
            self.log("Solicitando ticket de activación (raw)...")
            try:
                raw = backend.request_activation_ticket(udid)
                self.after(0, lambda: self._set_server_text(raw[:20000]))
                self.log("Ticket recibido (raw mostrado).")
                try:
                    self.log_structured("Activation ticket", {"raw_preview": raw[:1500]}, level="INFO", category="SERVER")
                except Exception:
                    pass
            except Exception as e:
                self.log(f"[ERROR] request_activation_ticket: {e}")
        threading.Thread(target=task, daemon=True).start()

    def _set_server_text(self, text):
        self.server_text.configure(state="normal")
        self.server_text.delete("0.0", "end")
        self.server_text.insert("0.0", text)
        self.server_text.configure(state="disabled")

    def restart_springboard(self):
        udid = self.current_udid
        if not udid:
            messagebox.showwarning("No device", "Conecta un dispositivo por USB primero.")
            return

        def task():
            self.log("Reiniciando SpringBoard...")
            try:
                out = backend.restart_springboard(udid)
                self.log("Reinicio solicitado. Output:\n" + (out or "sin salida"))
                try:
                    self.log_structured("SpringBoard restart", {"output": (out or "").strip()}, level="INFO", category="DEVICE")
                except Exception:
                    pass
            except Exception as e:
                self.log(f"[ERROR] restart_springboard: {e}")
        threading.Thread(target=task, daemon=True).start()

    def check_activation_status(self):
        """Comprueba el estado de activación / Activation Lock del dispositivo conectado."""
        udid = self.current_udid
        if not udid:
            messagebox.showwarning("No device", "Conecta un dispositivo por USB primero.")
            return

        def task():
            self.log("Comprobando estado de activación...")
            try:
                res = backend.get_activation_status(udid)
                state = res.get("activation_state") or "Desconocido"
                alock = bool(res.get("activation_lock"))
                out = f"Estado: {state}\nActivation Lock detectado: {'Sí' if alock else 'No'}\n\nRAW:\n{(res.get('raw') or '')[:2000]}"
                self.after(0, lambda: messagebox.showinfo("Estado de activación", out))
                try:
                    self.log_structured("Activation status", {"state": state, "activation_lock": alock, "raw_snippet": (res.get('raw') or '')[:800]}, level="INFO", category="DEVICE")
                except Exception:
                    pass
            except Exception as e:
                self.log(f"[ERROR] check_activation_status: {e}")
        threading.Thread(target=task, daemon=True).start()

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None

    def open_captive_portal(self):
        ip = self._get_local_ip()
        if not ip:
            messagebox.showerror("No IP", "No se pudo determinar la IP local. Asegúrate de estar en la misma red Wi‑Fi.")
            return
        url_http = f"http://{ip}:5000/"
        url_https = f"https://{ip}:5000/"
        try:
            self.clipboard_clear()
            self.clipboard_append(url_https)
        except Exception:
            pass
        try:
            webbrowser.open(url_http)
        except Exception:
            pass
        # popup con instrucciones y enlace al QR
        popup = ctk.CTkToplevel(self)
        popup.title("Abrir portal en iPhone / QR")
        popup.geometry("480x360")
        ctk.CTkLabel(popup, text="URL copiada al portapapeles. Abre Safari en tu iPhone o escanea el QR.", wraplength=440).pack(padx=12, pady=(12,8))
        ctk.CTkLabel(popup, text=url_https, text_color="#00A2E6", wraplength=440).pack(padx=12, pady=(0,8))
        def open_qr():
            qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=" + urllib.parse.quote_plus(url_https)
            try:
                webbrowser.open(qr_url)
            except Exception:
                pass
        ctk.CTkButton(popup, text="Abrir QR en navegador", command=open_qr, fg_color="#007ACC").pack(pady=(8,6), padx=12)
        # botón rápido para generar Recovery PDF desde la app
        ctk.CTkButton(popup, text="Generar Recovery PDF (desde servidor)", command=lambda: webbrowser.open(url_http + 'recovery-kit'), fg_color="#7046FF").pack(pady=(6,6))
        ctk.CTkButton(popup, text="Descargar certificado (server.crt)", command=lambda: webbrowser.open(url_http + 'certs/server.crt'), fg_color="#0066CC").pack(pady=(6,6))
        ctk.CTkButton(popup, text="Cerrar", command=popup.destroy, fg_color="#005B5B").pack(pady=(6,12))

    def generate_recovery_pdf(self):
        # diálogo simple para solicitar datos y generar el PDF localmente

        # diálogo simple para solicitar datos y generar el PDF localmente
        try:
            import tkinter.simpledialog as simpledialog
        except Exception:
            simpledialog = tk
        model = simpledialog.askstring('Recovery kit', 'Modelo (ej. iPhone X):')
        serial = simpledialog.askstring('Recovery kit', 'Número de serie:')
        udid = simpledialog.askstring('Recovery kit', 'UDID (opcional):')
        imei = simpledialog.askstring('Recovery kit', 'IMEI (opcional):')
        ios = simpledialog.askstring('Recovery kit', 'iOS version (opcional):')
        if not serial and not udid:
            messagebox.showwarning('Recovery kit', 'Introduce al menos el número de serie o UDID.')
            return
        device = {'model': model or '', 'serial': serial or '', 'udid': udid or '', 'imei': imei or '', 'ios_version': ios or ''}
        try:
            import recovery_docs
            out = recovery_docs.generate_recovery_kit(device, requester_name='Soporte', out_path=f'recovery_kit_{serial or udid}.pdf', fmt='pdf')
        except Exception as e:
            # fallback a md si reportlab no está disponible
            try:
                import recovery_docs
                out = recovery_docs.generate_recovery_kit(device, requester_name='Soporte', out_path=f'recovery_kit_{serial or udid}.md', fmt='md')
            except Exception as e2:
                messagebox.showerror('Recovery kit', f'Error generando recovery kit: {e} / {e2}')
                return
        messagebox.showinfo('Recovery kit', f'Recovery kit generado: {out}')
        try:
            os.startfile(out)
        except Exception:
            pass

        # Intentar subir el recovery al portal (si está activo en esta máquina)
        try:
            import requests
            ip = self._get_local_ip()
            if ip:
                # prefer https if available
                for scheme in ('https', 'http'):
                    url = f"{scheme}://{ip}:5000/upload-recovery"
                    try:
                        with open(out, 'rb') as fh:
                            r = requests.post(url, files={'file': (os.path.basename(out), fh)}, timeout=6, verify=False)
                        if r.ok:
                            data = r.json()
                            if data.get('ok') and data.get('url'):
                                messagebox.showinfo('Recovery uploaded', f'Recovery subido y disponible en:\n{data.get("url")}')
                                break
                    except Exception:
                        continue
        except Exception:
            pass

    def toggle_server_profile_signing(self):
        """Toggle the server-side signing default via the portal's API."""
        try:
            import requests
        except Exception:
            messagebox.showerror('Signing', 'La librería requests no está disponible.')
            return
        val = bool(self.server_signing_var.get())
        try:
            r = requests.post('http://127.0.0.1:5000/set-signing', json={'enabled': val}, timeout=4)
            if not r.ok:
                # server may return JSON error
                try:
                    err = r.json().get('error')
                except Exception:
                    err = r.text
                raise RuntimeError(err)
            j = r.json()
            self.server_signing_var.set(bool(j.get('enabled')))
            messagebox.showinfo('Signing', f"Firma server-side {'habilitada' if j.get('enabled') else 'deshabilitada'}")
        except Exception as e:
            messagebox.showerror('Signing', f'No se pudo cambiar la configuración del servidor: {e}')
            # refresh UI state
            self.after(200, self.refresh_server_signing_status)

    def refresh_server_signing_status(self):
        """Consulta el estado de firma del servidor y actualiza la UI."""
        try:
            import requests
            r = requests.get('http://127.0.0.1:5000/signing-status', timeout=3)
            if not r.ok:
                return
            j = r.json()
            self.server_signing_var.set(bool(j.get('enabled')))
        except Exception:
            # no-op (servidor no alcanzable)
            pass

    def enable_https_on_portal(self):
        """Solicita regenerar certificados al portal y forzar reload (si el portal está en la misma máquina)."""
        try:
            import requests
        except Exception:
            messagebox.showerror('HTTPS', 'La librería requests no está disponible.')
            return
        ip = '127.0.0.1'
        base = f'http://{ip}:5000'
        try:
            r = requests.post(base + '/generate-ssl', timeout=6)
            if not r.ok:
                raise RuntimeError('generate-ssl failed')
            # reload server to pick up certs
            requests.post(base + '/reload', timeout=6)
            # esperar a que HTTPS esté disponible
            import time, urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            start = time.time()
            ok = False
            while time.time() - start < 8:
                try:
                    rr = requests.get('https://127.0.0.1:5000/', timeout=2, verify=False)
                    if rr.status_code == 200:
                        ok = True
                        break
                except Exception:
                    time.sleep(0.6)
            if ok:
                messagebox.showinfo('HTTPS', 'Portal HTTPS habilitado en https://127.0.0.1:5000 (auto‑firmado).')
            else:
                messagebox.showwarning('HTTPS', 'Se generaron los certificados pero no se detectó HTTPS activo. Reinicia el servidor manualmente si es necesario.')
        except Exception as e:
            messagebox.showerror('HTTPS', f'No se pudo habilitar HTTPS: {e}')

    def show_install_guide(self):
        popup = ctk.CTkToplevel(self)
        popup.title('Guía: instalar perfil + certificado en iOS')
        popup.geometry('560x420')
        steps = (
            '1) Conecta el iPhone a la misma red Wi‑Fi que este equipo.\n'
            '2) Abre Safari en el iPhone y visita: https://{ip}:5000/ (o escribe la URL en el campo "Go to...").\n'
            '3) Pulsa "Descargar perfil" y acepta la instalación del perfil en Ajustes → Perfil descargado → Instalar.\n'
            '4) Descarga también el certificado: pulsa "Descargar certificado" y, en iOS, ve a Ajustes → General → Información → Ajustes de confianza de certificados y habilita la confianza para el certificado instalado.\n'
            '5) Reinicia la conexión Wi‑Fi si es necesario.\n'
            'Nota: instale perfil y certificado solo en dispositivos de su propiedad o con permiso explícito.'
        )
        ctk.CTkLabel(popup, text='Guía rápida — Instalar perfil y certificado', font=ctk.CTkFont(size=14, weight='bold')).pack(padx=12, pady=(12,6))
        ctk.CTkTextbox(popup, height=260, width=520, corner_radius=6).pack(padx=12, pady=(6,12))
        tb = popup.winfo_children()[-1]
        tb.configure(state='normal')
        tb.insert('0.0', steps)
        tb.configure(state='disabled')
        btn_frame = ctk.CTkFrame(popup)
        btn_frame.pack(padx=12, pady=(6,12))
        ctk.CTkButton(btn_frame, text='Abrir portal', command=self.open_captive_portal, width=180).pack(side='left', padx=6)
        ctk.CTkButton(btn_frame, text='Descargar certificado', command=lambda: webbrowser.open('http://127.0.0.1:5000/certs/server.crt'), width=180).pack(side='left', padx=6)
        ctk.CTkButton(popup, text='Cerrar', command=popup.destroy, fg_color='#005B5B').pack(pady=(6,12))

    def toggle_hotspot(self):
        """Intenta crear/alternar un hotspot Windows con netsh. Requiere privilegios de administrador y driver compatible."""
        if os.name != 'nt':
            messagebox.showerror('Hotspot', 'La creación de hotspot solo está soportada en Windows desde esta herramienta.')
            return
        import subprocess
        # comprobar estado
        def run(cmd):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, shell=True)
                return r.returncode, r.stdout + r.stderr
            except Exception as e:
                return 1, str(e)
        # intentar detener primero (toggle behavior)
        rc, out = run('netsh wlan stop hostednetwork')
        # configurar SSID/password
        ssid = f'Jarvis_Portal_{int(time.time())%1000}'
        pwd = 'jarvisportal123'
        rc2, out2 = run(f'netsh wlan set hostednetwork mode=allow ssid="{ssid}" key="{pwd}"')
        if rc2 != 0:
            messagebox.showerror('Hotspot', f'No se pudo configurar el hotspot. Salida:\n{out2}')
            return
        rc3, out3 = run('netsh wlan start hostednetwork')
        if rc3 != 0:
            messagebox.showerror('Hotspot', f'No se pudo iniciar el hotspot. Salida:\n{out3}\nNota: el driver puede no soportar hostednetwork o se requieren permisos de administrador.')
            return
        # hotspot iniciado
        url = f'http://{self._get_local_ip()}:5000/'
        self.clipboard_clear(); self.clipboard_append(url)
        messagebox.showinfo('Hotspot iniciado', f'Hotspot iniciado: {ssid}\nContraseña: {pwd}\nURL del portal copiada al portapapeles:\n{url}\nConecta el iPhone a la red Wi‑Fi creada para que se abra el portal cautivo automáticamente.')

        # Keep compatibility: show_dns_instructions implementation
        pass

    def show_dns_instructions(self):
        txt = (
            "Bypass DNS HUD — Instrucciones (visual):\n\n"
            "1) Abrir Ajustes → Wi‑Fi\n"
            "2) Pulsar (i) sobre la red → Configurar DNS → Manual\n"
            "3) Añadir DNS público (por ejemplo 1.1.1.1) y guardar\n"
            "4) Reiniciar conexión Wi‑Fi\n\n"
            "Nota: Este es un instructivo; algunos bypass requieren herramientas avanzadas."
        )
        messagebox.showinfo("Bypass DNS HUD — Instrucciones", txt)


    def export_logs(self):
        """Exporta el contenido de la consola a `logs/jarvis_logs_YYYYMMDD_HHMMSS.txt` y JSON estructurado."""
        import json
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        try:
            content = self.console.get("1.0", "end")
        except Exception:
            content = ""
        fname_base = time.strftime("jarvis_logs_%Y%m%d_%H%M%S")
        txt_path = os.path.join(logs_dir, fname_base + ".txt")
        json_path = os.path.join(logs_dir, fname_base + ".json")
        with open(txt_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        # build structured export from history
        structured = []
        for item in self.log_history:
            if isinstance(item, tuple) and item and item[0] == "STRUCT":
                _, ts, title, level, category, data = item
                structured.append({"ts": ts, "title": title, "level": level, "category": category, "data": data})
            else:
                structured.append({"text": str(item)})
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump({"exported_at": time.strftime("%Y-%m-%d %H:%M:%S"), "structured": structured, "raw_text": content}, jf, ensure_ascii=False, indent=2)
        messagebox.showinfo("Exportar logs", f"Logs exportados a:\n{txt_path}\n{json_path}")

    def open_logs_folder(self):
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        try:
            os.startfile(logs_dir)
        except Exception:
            messagebox.showinfo("Abrir carpeta de logs", f"Ruta de logs:\n{logs_dir}")

    # ---- Settings handlers ----
    def _on_toggle_colorize(self):
        self.colorize_logs = bool(self.colorize_var.get())
        self.update_log_view()

    def _on_change_max_value_length(self, v):
        try:
            val = int(float(v))
        except Exception:
            return
        self.max_value_length = val
        if hasattr(self, '_max_value_label'):
            self._max_value_label.configure(text=f"Current: {self.max_value_length}")
        # re-render logs with new truncation
        self.update_log_view()

    # ---- Logging ----
    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        text = f"[{ts}] {msg}\n"
        # store in history for filtration/export
        try:
            self.log_history.append(text)
        except Exception:
            pass
        self.log_queue.put(text)

    def _process_log_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                # keep history (already appended in log/log_structured) - ensure duplication avoided
                self.console.configure(state="normal")
                # structured log tuple -> ("STRUCT", ts, title, level, category, data)
                if isinstance(item, tuple) and item and item[0] == "STRUCT":
                    _, ts, title, level, category, data = item
                    self._insert_structured_log(ts, title, level, category, data)
                else:
                    line = str(item)
                    tag = "info"
                    if line.startswith("[") and "ERROR" in line:
                        tag = "error"
                    elif line.startswith("[") and ("WARN" in line or "WARNING" in line):
                        tag = "warning"
                    self.console.insert("end", line, tag)
                self.console.see("end")
                self.console.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._process_log_queue)

    def update_log_view(self):
        """Re-render the console from `self.log_history` applying filters and search."""
        try:
            self.console.configure(state="normal")
            self.console.delete("1.0", "end")
            # gather filter settings
            show_info = bool(self.filter_info_var.get())
            show_warn = bool(self.filter_warn_var.get())
            show_error = bool(self.filter_error_var.get())
            show_device = bool(self.filter_device_var.get())
            show_owner = bool(self.filter_owner_var.get())
            show_panics = bool(self.filter_panics_var.get())
            show_server = bool(self.filter_server_var.get())
            text_filter = (self.filter_text_var.get() or "").strip().lower()

            def level_allowed(level):
                if not level:
                    return True
                lv = level.upper()
                if lv.startswith("ERR"):
                    return show_error
                if lv.startswith("W"):
                    return show_warn
                return show_info

            def category_allowed(cat):
                if not cat:
                    return True
                c = cat.upper()
                if c == "DEVICE":
                    return show_device
                if c == "OWNER":
                    return show_owner
                if c == "PANICS":
                    return show_panics
                if c == "SERVER":
                    return show_server
                return True

            for item in list(self.log_history):
                if isinstance(item, tuple) and item and item[0] == "STRUCT":
                    _, ts, title, level, category, data = item
                    if not level_allowed(level) or not category_allowed(category):
                        continue
                    # apply text filter
                    if text_filter:
                        hay = title.lower() + " " + (category or "") + " " + str(data).lower()
                        if text_filter not in hay:
                            continue
                    self._insert_structured_log(ts, title, level, category, data)
                else:
                    line = str(item)
                    # derive level/category heuristically
                    line_low = line.lower()
                    if "error" in line_low and not show_error:
                        continue
                    if ("warn" in line_low or "warning" in line_low) and not show_warn:
                        continue
                    # category heuristics
                    if ("device" in line_low or "udid" in line_low) and not show_device:
                        continue
                    if ("owner" in line_low or "email" in line_low) and not show_owner:
                        continue
                    if ("panic" in line_low or "crash" in line_low) and not show_panics:
                        continue
                    if text_filter and text_filter not in line_low:
                        continue
                    tag = "info"
                    if "error" in line_low:
                        tag = "error"
                    elif "warn" in line_low or "warning" in line_low:
                        tag = "warning"
                    self.console.insert("end", line, tag)
            self.console.see("end")
        finally:
            self.console.configure(state="disabled")


if __name__ == "__main__":
    app = JarvisApp()
    app.mainloop()
