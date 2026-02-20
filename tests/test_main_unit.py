import os
import json
import queue
import pytest
import main
from main import JarvisApp


class FakeVar:
    def __init__(self, v):
        self._v = v

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


def _fake_init(self):
    # minimal headless attributes required by the tested methods
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


def test_log_appends_and_queue(monkeypatch):
    monkeypatch.setattr(JarvisApp, "__init__", _fake_init)
    app = JarvisApp()

    app.log("hello world")

    # history appended
    assert any("hello world" in str(h) for h in app.log_history)

    # queue receives the logged line
    q_item = app.log_queue.get_nowait()
    assert "hello world" in q_item


def test_log_structured_and_process_queue(monkeypatch):
    monkeypatch.setattr(JarvisApp, "__init__", _fake_init)
    app = JarvisApp()

    app.log_structured("Sometitle", {"k": "v"}, level="ERROR", category="PANICS")

    # last history entry is a structured tuple
    assert app.log_history
    last = app.log_history[-1]
    assert isinstance(last, tuple) and last[0] == "STRUCT"
    assert last[2] == "Sometitle"

    # process queued structured entry and verify console output
    app._process_log_queue()
    buf = app.console.get("1.0", "end")
    assert "Sometitle" in buf
    assert "k: v" in buf
    assert "ERROR" in buf or "[ERROR]" in buf


def test_update_log_view_respects_filters_and_search(monkeypatch):
    monkeypatch.setattr(JarvisApp, "__init__", _fake_init)
    app = JarvisApp()

    # populate history with mixed entries
    app.log_history.append(("STRUCT", "01:00:00", "Device found", "INFO", "DEVICE", {"udid": "X"}))
    app.log_history.append(("STRUCT", "01:00:01", "Owner data", "INFO", "OWNER", {"email_masked": "a@b"}))
    app.log_history.append("[00:00:00] Random ERROR happened\n")

    # default: all visible
    app.update_log_view()
    buf = app.console.get("1.0", "end")
    assert "Device found" in buf and "Owner data" in buf and "Random ERROR happened" in buf

    # hide DEVICE category
    app.filter_device_var.set(False)
    app.update_log_view()
    buf = app.console.get("1.0", "end")
    assert "Device found" not in buf
    assert "Owner data" in buf

    # hide ERROR level
    app.filter_error_var.set(False)
    app.update_log_view()
    buf = app.console.get("1.0", "end")
    assert "Random ERROR happened" not in buf

    # text search
    app.filter_text_var.set("owner")
    app.filter_device_var.set(True)
    app.filter_error_var.set(True)
    app.update_log_view()
    buf = app.console.get("1.0", "end")
    assert "Owner data" in buf and "Device found" not in buf


def test_export_logs_writes_json_and_includes_structured(monkeypatch, tmp_path):
    monkeypatch.setattr(JarvisApp, "__init__", _fake_init)
    app = JarvisApp()

    # prepare console and structured history
    app.console._buf = "Line A\n"
    app.log_history.append(("STRUCT", "02:02:02", "Title", "INFO", "OTHER", {"a": "b"}))

    # isolate logs directory into tmp_path
    monkeypatch.setattr(main, "__file__", str(tmp_path / "main.py"))
    monkeypatch.setattr(main.messagebox, "showinfo", lambda *a, **k: None)

    app.export_logs()

    logs_dir = tmp_path / "logs"
    files = sorted([p for p in logs_dir.iterdir() if p.name.startswith("jarvis_logs_") and p.suffix == ".json"], key=lambda p: p.stat().st_mtime, reverse=True)
    assert files, "No JSON export created"

    with open(files[0], "r", encoding="utf-8") as fh:
        data = json.load(fh)

    assert any(entry.get("title") == "Title" for entry in data.get("structured", []))
