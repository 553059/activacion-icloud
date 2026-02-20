"""
Headless button-press simulation for JarvisApp.
This script monkeypatches JarvisApp.__init__ with the minimal _fake_init used in tests,
creates an instance and calls common button handlers in sequence.
Designed to be safe for interactive use (suppresses messagebox/webbrowser popups).
"""
import time
import os, sys
# ensure project root is on sys.path so `import main` works when script runs from scripts/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import main
from main import JarvisApp

# minimal headless init copied from tests
def _fake_init(self):
    class _SimpleLabel:
        def __init__(self, text=""):
            self._text = text
        def configure(self, **kw):
            if "text" in kw:
                self._text = kw["text"]
        def cget(self, key):
            if key == "text":
                return self._text
            return None
        def pack(self, *a, **k):
            pass
        def grid(self, *a, **k):
            pass

    class _SimpleTextbox:
        def __init__(self, text=""):
            self._buf = text
            self._state = "normal"
        def configure(self, **kw):
            if "state" in kw:
                self._state = kw["state"]
        def delete(self, start, end):
            self._buf = ""
        def insert(self, index, text, *args):
            self._buf += text
        def get(self, start, end):
            return self._buf

    class _SimpleConsole(_SimpleTextbox):
        def see(self, *a, **k):
            pass

    import queue
    self.device_info_text = _SimpleLabel("Esperando dispositivo...")
    self.device_status_label = _SimpleLabel("Ningún dispositivo detectado")
    self.dashboard_detail = _SimpleTextbox("")
    self.console = _SimpleConsole()
    self.log_history = []
    self.log_queue = queue.Queue()
    self.current_udid = None

    # rendering / truncation settings used by _insert_structured_log
    self.max_value_length = 1000
    self.max_list_item_length = 300
    self.snippet_length = 800
    self.colorize_logs = True

    # filter variables used by update_log_view
    class FakeVar:
        def __init__(self, v):
            self._v = v
        def get(self):
            return self._v
        def set(self, v):
            self._v = v

    self.filter_info_var = FakeVar(True)
    self.filter_warn_var = FakeVar(True)
    self.filter_error_var = FakeVar(True)
    self.filter_device_var = FakeVar(True)
    self.filter_owner_var = FakeVar(True)
    self.filter_panics_var = FakeVar(True)
    self.filter_server_var = FakeVar(True)
    self.filter_text_var = FakeVar("")

    # no-op scheduler to avoid Tk `after` calls
    self.after = lambda *a, **k: None


# suppress blocking popups / browser opens
main.messagebox.showinfo = lambda *a, **k: None
main.messagebox.showwarning = lambda *a, **k: None
main.messagebox.showerror = lambda *a, **k: None
main.messagebox.askyesno = lambda *a, **k: True
# stub backend activation functions so headless sequence can exercise the activation button safely
main.backend.request_activation_ticket = lambda udid: '<xml>TICKET</xml>'
main.backend.perform_activation = lambda udid, ticket: 'ACTIVATED'
import webbrowser
webbrowser.open = lambda *a, **k: None

# apply headless init
JarvisApp.__init__ = _fake_init
app = JarvisApp()
# stub clipboard functions (headless environment)
app.clipboard_clear = lambda: None
app.clipboard_append = lambda v: None

sequence = [
    ("restart_springboard", app.restart_springboard),
    ("check_activation_status", app.check_activation_status),
    ("open_captive_portal", app.open_captive_portal),
    ("activate_device", app.activate_device),
    ("extract_owner_intel", app.extract_owner_intel),
    ("analyze_panics", app.analyze_panics),
    ("enable_https_on_portal", app.enable_https_on_portal),
    ("toggle_hotspot", app.toggle_hotspot),
    ("export_logs", app.export_logs),
]

for name, fn in sequence:
    app.log(f"[SIM] Ejecutando: {name}")
    try:
        fn()
    except Exception as e:
        # ensure any exception is visible both in stdout and in live.log
        app.log(f"[SIM][ERROR] {name}: {e}")
    time.sleep(0.15)

app.log('[SIM] Secuencia completada')
print('headless sequence done')
