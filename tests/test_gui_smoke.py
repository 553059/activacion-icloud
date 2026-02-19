import os
import time
import sys
import pytest
import backend_modules as bm
import main
from main import JarvisApp


@pytest.mark.skipif(sys.platform.startswith("linux") and os.environ.get("CI") == "true", reason="Headless CI - skipping GUI test")
def test_gui_update_device_panel(tmp_path, monkeypatch):
    # prevent background poll_device from blocking by mocking backend device calls
    monkeypatch.setattr(bm, "list_devices", lambda: [])
    monkeypatch.setattr(bm, "get_device_info", lambda udid: {})

    # --- Headless shim: replace JarvisApp.__init__ so no real GUI is created ---
    class _SimpleLabel:
        def __init__(self, text=""):
            self._text = text
        def configure(self, **kw):
            if 'text' in kw:
                self._text = kw['text']
        def cget(self, key):
            if key == 'text':
                return self._text
            return None
        def pack(self, *a, **k):
            pass
        def grid(self, *a, **k):
            pass

    class _SimpleTextbox:
        def __init__(self, text=""):
            self._buf = text
            self._state = 'normal'
        def configure(self, **kw):
            if 'state' in kw:
                self._state = kw['state']
        def delete(self, start, end):
            self._buf = ''
        def insert(self, index, text):
            self._buf += text
        def get(self, start, end):
            return self._buf

    class _SimpleConsole(_SimpleTextbox):
        def see(self, *a, **k):
            pass

    def _fake_init(self):
        # minimal attributes used by the test and by methods called (_update_device_ui/export_logs)
        self.device_info_text = _SimpleLabel("Esperando dispositivo...")
        self.device_status_label = _SimpleLabel("Ningún dispositivo detectado")
        self.dashboard_detail = _SimpleTextbox("")
        self.console = _SimpleConsole()
        self.log_history = []
        self.current_udid = None

    # patch the constructor and messagebox dialogs to avoid GUI popups
    monkeypatch.setattr(JarvisApp, '__init__', _fake_init)
    monkeypatch.setattr(main.messagebox, 'showinfo', lambda *a, **k: None)
    monkeypatch.setattr(main.messagebox, 'showwarning', lambda *a, **k: None)

    # create app instance (headless)
    app = JarvisApp()
    try:
        fake_info = {
            "udid": "FAKE-UDID-1",
            "model": "iPhoneTest",
            "serial": "SER123",
            "imei": "356000000000001",
            "battery_percent": "78",
            "battery_cycles": "20",
            "ios_version": "16.4",
        }
        # call UI update directly
        app._update_device_ui(fake_info)
        # ensure labels updated
        assert "FAKE-UDID-1" in app.device_info_text.cget("text")
        assert "OK" in app.device_status_label.cget("text")

        # test export logs creates a file
        app.console.configure(state="normal")
        app.console.delete("1.0", "end")
        app.console.insert("1.0", "Test log line\n")
        app.console.configure(state="disabled")
        app.export_logs()
        logs_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
        logs_dir = os.path.abspath(logs_dir)
        # newest file in logs dir
        files = sorted([f for f in os.listdir(logs_dir)], reverse=True)
        assert any(f.startswith("jarvis_logs_") for f in files)
    finally:
        # destroy GUI to free resources (no-op for headless shim)
        try:
            app.destroy()
        except Exception:
            pass
