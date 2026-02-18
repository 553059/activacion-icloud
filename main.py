# main.py
import threading
import queue
import time
import os
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

    def _add_sidebar_buttons(self, parent):
        ctk.CTkLabel(parent, text="JARVIS ING", font=ctk.CTkFont(size=18, weight="bold"), text_color="#00E6E6").pack(pady=(18,8))
        nav = [
            ("Inicio", self.show_dashboard),
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

        # Diagnostic / Owner Intel
        f2 = ctk.CTkFrame(self.main_frame)
        self.frames["diagnostic"] = f2
        self._populate_diagnostic(f2)

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
        ctk.CTkLabel(f5, text="Logs exportados a `logs/` (automático)").pack(padx=20, pady=(8,20))

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
        self.console = scrolledtext.ScrolledText(parent, bg="#071923", fg="#E6FFFF", insertbackground="#E6FFFF", height=8)
        self.console.pack(fill="both", expand=True, padx=8, pady=8)
        self.console.configure(state="disabled", font=("Consolas", 10))

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
            except Exception as e:
                self.log(f"[ERROR] analyze_panics: {e}")
        threading.Thread(target=task, daemon=True).start()

    def _set_panics_text(self, text):
        self.panics_text.configure(state="normal")
        self.panics_text.delete("0.0", "end")
        self.panics_text.insert("0.0", text)
        self.panics_text.configure(state="disabled")

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
            except Exception as e:
                self.log(f"[ERROR] restart_springboard: {e}")
        threading.Thread(target=task, daemon=True).start()

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
        """Exporta el contenido de la consola a `logs/jarvis_logs_YYYYMMDD_HHMMSS.txt`"""
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        try:
            content = self.console.get("1.0", "end")
        except Exception:
            content = ""
        fname = time.strftime("jarvis_logs_%Y%m%d_%H%M%S.txt")
        path = os.path.join(logs_dir, fname)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        messagebox.showinfo("Exportar logs", f"Logs exportados a:\n{path}")

    def open_logs_folder(self):
        logs_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        try:
            os.startfile(logs_dir)
        except Exception:
            messagebox.showinfo("Abrir carpeta de logs", f"Ruta de logs:\n{logs_dir}")

    # ---- Logging ----
    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{ts}] {msg}\n")

    def _process_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.console.configure(state="normal")
                self.console.insert("end", line)
                self.console.see("end")
                self.console.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._process_log_queue)


if __name__ == "__main__":
    app = JarvisApp()
    app.mainloop()
