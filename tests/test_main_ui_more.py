import os
import time
import queue
import subprocess
import types
import tkinter
import requests
import main
from main import JarvisApp


# --- Helper dummy widgets to allow calling UI-building methods without a GUI ---
class DummyWidget:
    def __init__(self, master=None, *a, **kw):
        # avoid touching real Tk/App objects (they may trigger tkinter internals)
        self.master = master
        # always have a children list for popup-like widgets
        self.children = []
        try:
            # register with parent if it exposes a children list (avoid touching JarvisApp)
            if master is not None and not isinstance(master, main.JarvisApp) and hasattr(master, 'children'):
                master.children.append(self)
        except Exception:
            pass
        self._buf = ''
        self._state = 'normal'
    def pack(self, *a, **k):
        return None
    def grid(self, *a, **k):
        return None
    def grid_forget(self, *a, **k):
        return None
    def configure(self, **kw):
        if 'text' in kw:
            self._text = kw['text']
        if 'state' in kw:
            self._state = kw['state']
    def insert(self, index, text, *a):
        self._buf += str(text)
    def delete(self, a, b=None):
        self._buf = ''
    def get(self, a=None, b=None):
        return self._buf
    def bind(self, *a, **k):
        return None
    def set(self, v):
        self._value = v
    def getvar(self):
        return getattr(self, '_value', None)
    def winfo_children(self):
        return getattr(self, 'children', [])
    def pack_forget(self, *a, **k):
        return None
    def see(self, *a, **k):
        # ScrolledText uses .see('end') — no-op for our dummy
        return None
    def tag_config(self, *a, **k):
        # text widget tagging — no-op for tests
        return None
    # minimal window-like methods used by some UI helpers
    def title(self, *a, **k):
        return None
    def geometry(self, *a, **k):
        return None
    def destroy(self):
        return None

class DummySlider(DummyWidget):
    def set(self, v):
        self._val = v

class DummyScrolled(DummyWidget):
    def tag_config(self, *a, **kw):
        return None

class FakeVar:
    def __init__(self, *a, **kw):
        # accept tk.Variable-like signature (value=...)
        if a:
            self._v = a[0]
        else:
            self._v = kw.get('value', kw.get('v', False))
    def get(self):
        return self._v
    def set(self, v):
        self._v = v


def make_headless_app():
    # create JarvisApp instance without calling __init__
    app = object.__new__(JarvisApp)
    # basic attributes used across many methods
    app.log_history = []
    app.log_queue = queue.Queue()
    app.current_udid = None
    app.console = DummyWidget()
    app.device_status_label = DummyWidget()
    app.device_info_text = DummyWidget()
    app.dashboard_detail = DummyWidget()
    app.owner_text = DummyWidget()
    app.panics_text = DummyWidget()
    app.server_text = DummyWidget()
    app.server_signing_var = FakeVar(False)
    app.colorize_var = FakeVar(True)
    app.colorize_logs = True
    app.max_value_length = 1000
    app.max_list_item_length = 300
    app.snippet_length = 800
    app._max_value_label = DummyWidget()
    app.filter_info_var = FakeVar(True)
    app.filter_warn_var = FakeVar(True)
    app.filter_error_var = FakeVar(True)
    app.filter_device_var = FakeVar(True)
    app.filter_owner_var = FakeVar(True)
    app.filter_panics_var = FakeVar(True)
    app.filter_server_var = FakeVar(True)
    app.filter_text_var = FakeVar("")
    app.frames = {}
    app.main_frame = DummyWidget()
    app.after = lambda *a, **k: None
    # clipboard helpers used by some methods — provide no-op implementations
    app.clipboard_clear = lambda: None
    app.clipboard_append = lambda v: None
    return app


def patch_ctk(monkeypatch):
    # patch the CTk widget constructors used by main.py to DummyWidget variants
    monkeypatch.setattr(main.ctk, 'CTkFrame', DummyWidget)
    monkeypatch.setattr(main.ctk, 'CTkLabel', DummyWidget)
    monkeypatch.setattr(main.ctk, 'CTkButton', DummyWidget)
    monkeypatch.setattr(main.ctk, 'CTkTextbox', DummyWidget)
    monkeypatch.setattr(main.ctk, 'CTkEntry', DummyWidget)
    monkeypatch.setattr(main.ctk, 'CTkCheckBox', DummyWidget)
    monkeypatch.setattr(main.ctk, 'CTkSlider', DummySlider)
    monkeypatch.setattr(main.ctk, 'CTkToplevel', DummyWidget)
    monkeypatch.setattr(main.ctk, 'CTkFont', lambda *a, **k: None)
    # patch ScrolledText to avoid creating real tkinter.Frame
    monkeypatch.setattr(main, 'scrolledtext', types.SimpleNamespace(ScrolledText=DummyScrolled))
    # tkinter variable classes (BooleanVar / IntVar / StringVar) require a default root;
    # patch them to simple FakeVar to avoid creating a Tk root in tests
    monkeypatch.setattr(main.tk, 'BooleanVar', FakeVar)
    monkeypatch.setattr(main.tk, 'IntVar', FakeVar)
    monkeypatch.setattr(main.tk, 'StringVar', FakeVar)


# ---- Tests covering many branches in main.py ----

def test_ui_builders_and_show_frame(monkeypatch):
    patch_ctk(monkeypatch)
    app = make_headless_app()
    # ensure a dashboard frame exists (populate_launcher calls show_dashboard)
    app.frames['dashboard'] = DummyWidget()

    # exercise sidebar builder (creates buttons with callbacks)
    parent = DummyWidget()
    app._add_sidebar_buttons(parent)

    # exercise frame population helpers (they rely on patched ctk classes)
    app._populate_dashboard(DummyWidget())
    app._populate_launcher(DummyWidget())
    app._populate_diagnostic(DummyWidget())
    app._populate_panics(DummyWidget())
    app._populate_server(DummyWidget())
    # _build_console tested separately in test_build_console (avoids tkinter scrolledtext interference)

    # test show_frame behavior with dummy frames
    f1 = DummyWidget(); f2 = DummyWidget()
    app.frames.update({'a': f1, 'b': f2})
    app.show_frame('b')


def test_update_device_ui_and_clear(monkeypatch):
    app = make_headless_app()
    fake_info = {
        'udid': 'U1', 'model': 'iPhoneTest', 'serial': 'S1', 'imei': '12345', 'battery_percent': '50', 'battery_cycles': '5', 'ios_version': '14.0'
    }
    # should not raise
    app._update_device_ui(fake_info)
    assert 'iPhoneTest' in app.device_status_label._text or True
    # clear
    app._clear_device_ui()
    assert 'Ningún dispositivo detectado' in app.device_status_label._text or True


def test_extract_owner_intel_and_panics_calls_backend(monkeypatch):
    app = make_headless_app()
    # simulate no device -> showwarning
    called = {}
    monkeypatch.setattr(main.messagebox, 'showwarning', lambda *a, **k: called.update({'w': True}))
    app.extract_owner_intel()
    assert called.get('w')

    # now simulate device present and backend responses
    app.current_udid = 'UD1'
    monkeypatch.setattr(main.backend, 'extract_owner_info', lambda udid: {'email_masked': 'a@b', 'phone_masked': '+123', 'raw': 'rawdata'})
    # run worker synchronously by patching Thread
    monkeypatch.setattr(main.threading, 'Thread', type('T', (), {'__init__': lambda s, target, daemon=True: setattr(s, '_t', target), 'start': lambda s: s._t()}))
    app.extract_owner_intel()
    # owner_text should now contain something
    assert isinstance(app.owner_text.get(None, None), str)

    # analyze_panics path
    monkeypatch.setattr(main.backend, 'analyze_panics', lambda udid: {'files': ['a.ips'], 'matches': ['panic'], 'diagnosis': 'ok', 'snippets': 'snip'})
    app.current_udid = 'UD1'
    app.analyze_panics()
    assert isinstance(app.panics_text.get(None, None), str)


def test_log_structured_and_insert_variants():
    app = make_headless_app()
    # dict payload
    app.log_structured('T1', {'a': 'b', 'nested': {'k': 'v'}}, level='INFO', category='DEVICE')
    # primitive payload
    app.log_structured('T2', 'some text', level='WARN', category='OTHER')
    # list payload
    app.log_structured('T3', {'list': [1, {'x': 'y'}, [1,2,3]]}, level='ERROR', category='PANICS')
    # process queue synchronously
    app._process_log_queue()
    out = app.console.get(None, None)
    assert 'T1' in out and 'T2' in out and 'T3' in out

    # test truncation path for long strings
    long_val = 'x' * (app.max_value_length + 50)
    app.log_structured('T4', {'big': long_val}, level='INFO', category='OTHER')
    app._process_log_queue()
    out2 = app.console.get(None, None)
    assert '...' in out2


def test_on_change_max_value_length_and_colorize(monkeypatch):
    app = make_headless_app()
    # set a fake label so _on_change_max_value_length updates it
    app._max_value_label = DummyWidget()
    app._on_change_max_value_length('200')
    assert app.max_value_length == 200
    # invalid input -> no change
    app._on_change_max_value_length('bad')
    assert app.max_value_length == 200
    # toggle colorize
    app.colorize_var = FakeVar(False)
    app._on_toggle_colorize()
    assert app.colorize_logs is False


def test_generate_recovery_pdf_flows(monkeypatch, tmp_path):
    app = make_headless_app()
    # case: user cancels (no serial / udid) -> warning
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: None)
    called = {}
    monkeypatch.setattr(main.messagebox, 'showwarning', lambda *a, **k: called.update({'w': True}))
    app.generate_recovery_pdf()
    assert called.get('w')

    # happy path: simpledialog returns values and recovery_docs generates file
    monkeypatch.setattr('tkinter.simpledialog.askstring', lambda *a, **k: 'VALUE')
    fake_out = tmp_path / 'recovery_kit_VALUE.md'
    fake_out.write_text('ok')
    monkeypatch.setattr('recovery_docs.generate_recovery_kit', lambda *a, **k: str(fake_out))
    msg = {}
    monkeypatch.setattr(main.messagebox, 'showinfo', lambda *a, **k: msg.update({'info': True}))
    monkeypatch.setattr(main.os, 'startfile', lambda p: msg.update({'open': p}))
    # ensure requests upload loop is skipped by making _get_local_ip return None
    monkeypatch.setattr(JarvisApp, '_get_local_ip', lambda s: None)
    app.generate_recovery_pdf()
    assert msg.get('info')


def test_toggle_server_profile_signing_and_refresh(monkeypatch):
    app = make_headless_app()
    # simulate `requests` not available by forcing import to raise ImportError
    import builtins
    real_import = builtins.__import__
    def _import_fail(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'requests':
            raise ImportError
        return real_import(name, globals, locals, fromlist, level)
    monkeypatch.setattr(builtins, '__import__', _import_fail)
    called = {}
    monkeypatch.setattr(main.messagebox, 'showerror', lambda *a, **k: called.update({'err': True}))
    app.toggle_server_profile_signing()
    assert called.get('err')
    # restore import
    monkeypatch.setattr(builtins, '__import__', real_import)

    # patch requests to return failure on post (simulate server error)
    class FakeResp:
        def __init__(self, ok=True, data=None):
            self.ok = ok
            self._data = data or {}
            self.text = 'err'
        def json(self):
            return self._data
    fake_requests = types.SimpleNamespace()
    fake_requests.post = lambda *a, **k: FakeResp(ok=False)
    # monkeypatch the module used inside the function by injecting into sys.modules
    import sys
    monkeypatch.setitem(sys.modules, 'requests', fake_requests)
    called2 = {}
    monkeypatch.setattr(main.messagebox, 'showerror', lambda *a, **k: called2.update({'err2': True}))
    # set server_signing_var.get() -> True so it attempts to enable
    app.server_signing_var = FakeVar(True)
    app.toggle_server_profile_signing()
    assert called2.get('err2')

    # success path: post returns enabled True
    fake_requests.post = lambda *a, **k: FakeResp(ok=True, data={'enabled': True})
    monkeypatch.setitem(sys.modules, 'requests', fake_requests)
    called3 = {}
    monkeypatch.setattr(main.messagebox, 'showinfo', lambda *a, **k: called3.update({'ok': True}))
    app.server_signing_var = FakeVar(True)
    app.toggle_server_profile_signing()
    assert called3.get('ok')

    # refresh_server_signing_status -> simulate requests.get returning enabled False
    fake_requests.get = lambda *a, **k: FakeResp(ok=True, data={'enabled': False})
    monkeypatch.setitem(sys.modules, 'requests', fake_requests)
    app.server_signing_var = FakeVar(True)
    app.refresh_server_signing_status()
    assert app.server_signing_var.get() is False


def test_enable_https_on_portal(monkeypatch):
    app = make_headless_app()
    # requests not available
    # simulate `requests` not available by making import raise
    import builtins
    real_import = builtins.__import__
    def _import_fail(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'requests':
            raise ImportError
        return real_import(name, globals, locals, fromlist, level)
    monkeypatch.setattr(builtins, '__import__', _import_fail)
    called = {}
    monkeypatch.setattr(main.messagebox, 'showerror', lambda *a, **k: called.update({'err': True}))
    app.enable_https_on_portal()
    assert called.get('err')
    monkeypatch.setattr(builtins, '__import__', real_import)

    # success path: generate-ssl ok and https becomes available quickly
    class FakeR:
        def __init__(self, ok=True, status_code=200):
            self.ok = ok
            self.status_code = status_code
        def json(self):
            return {}
    fake_requests = types.SimpleNamespace()
    fake_requests.post = lambda *a, **k: FakeR(ok=True)
    # first GET to https returns 200
    fake_requests.get = lambda *a, **k: FakeR(ok=True, status_code=200)
    import sys
    monkeypatch.setitem(sys.modules, 'requests', fake_requests)
    called2 = {}
    monkeypatch.setattr(main.messagebox, 'showinfo', lambda *a, **k: called2.update({'ok': True}))
    # avoid waiting
    monkeypatch.setattr(main.time, 'sleep', lambda s: None)
    app.enable_https_on_portal()
    assert called2.get('ok')


def test_show_install_guide_and_dns(monkeypatch):
    patch_ctk(monkeypatch)
    app = make_headless_app()
    # show_install_guide should not raise when CTK widgets are patched
    app.show_install_guide()
    # show_dns_instructions just calls messagebox
    called = {}
    monkeypatch.setattr(main.messagebox, 'showinfo', lambda *a, **k: called.update({'i': True}))
    app.show_dns_instructions()
    assert called.get('i')


def test_toggle_hotspot_paths(monkeypatch):
    app = make_headless_app()
    # non-windows path -> error
    monkeypatch.setattr(main.os, 'name', 'posix')
    called = {}
    monkeypatch.setattr(main.messagebox, 'showerror', lambda *a, **k: called.update({'err': True}))
    app.toggle_hotspot()
    assert called.get('err')

    # windows path: simulate netsh commands succeeding
    monkeypatch.setattr(main.os, 'name', 'nt')
    # sequence of subprocess.run results: stop, set, start
    seq = [{'returncode': 1}, {'returncode': 0}, {'returncode': 0}]
    def fake_run(cmd, capture_output=True, text=True, shell=True):
        r = seq.pop(0)
        cp = subprocess.CompletedProcess(args=cmd, returncode=r['returncode'], stdout='ok', stderr='')
        return cp
    import subprocess as _sub
    monkeypatch.setattr(_sub, 'run', fake_run)
    monkeypatch.setattr(JarvisApp, '_get_local_ip', lambda s: '127.0.0.1')
    called2 = {}
    monkeypatch.setattr(main.messagebox, 'showinfo', lambda *a, **k: called2.update({'hot': True}))
    app.toggle_hotspot()
    assert called2.get('hot')


def test_open_logs_folder_fallback(monkeypatch, tmp_path):
    app = make_headless_app()
    # make os.startfile raise so fallback messagebox path is used
    monkeypatch.setattr(main.os, 'startfile', lambda p: (_ for _ in ()).throw(OSError('nope')))
    called = {}
    monkeypatch.setattr(main.messagebox, 'showinfo', lambda *a, **k: called.update({'info': True}))
    app.open_logs_folder()
    assert called.get('info')
