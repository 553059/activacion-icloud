import threading
import socket
import webbrowser
import backend_modules as bm
import main
from main import JarvisApp


def _fake_init_extended(self):
    # minimal headless attributes for these tests (includes server_text)
    class _SimpleTextbox:
        def __init__(self, text=""):
            self._buf = text
            self._state = "normal"
        def configure(self, **kw):
            if 'state' in kw:
                self._state = kw['state']
        def delete(self, start, end):
            self._buf = ''
        def insert(self, index, text, *a):
            self._buf += text
        def get(self, start, end):
            return self._buf
        def see(self, *a, **k):
            pass
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
    self.device_info_text = _SimpleLabel()
    self.device_status_label = _SimpleLabel()
    self.dashboard_detail = _SimpleTextbox()
    self.console = _SimpleTextbox()
    self.log_history = []
    import queue as _queue
    self.log_queue = _queue.Queue()
    self.server_text = _SimpleTextbox()
    self.current_udid = None
    self.after = lambda *a, **k: None
    # filter vars used by other methods
    self.filter_info_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_warn_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_error_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_device_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_owner_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_panics_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_server_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_text_var = type('V',(object,),{'get': lambda s: ''})()


def test_restart_springboard_logs_and_handles_errors(monkeypatch):
    monkeypatch.setattr(JarvisApp, '__init__', _fake_init_extended)
    app = JarvisApp()

    # when no device -> warning branch (messagebox)
    called = {}
    monkeypatch.setattr(main.messagebox, 'showwarning', lambda *a, **k: called.update({'warn': True}))
    app.restart_springboard()
    assert called.get('warn')

    # now simulate device present and backend success
    app.current_udid = 'UD1'
    monkeypatch.setattr(bm, 'restart_springboard', lambda udid: 'OK')
    class ImmediateThread:
        def __init__(self, target, daemon=True):
            self._t = target
        def start(self):
            self._t()
    monkeypatch.setattr(threading, 'Thread', ImmediateThread)

    app.restart_springboard()
    # last log entry should indicate restart requested
    assert any('Reiniciando SpringBoard' in str(x) or 'Reinicio solicitado' in str(x) for x in app.log_history)

    # simulate backend raising -> should log an error
    def _fail(udid):
        raise RuntimeError('boom')
    app.current_udid = 'UD2'
    monkeypatch.setattr(bm, 'restart_springboard', _fail)
    app.restart_springboard()
    assert any('restart_springboard' in str(x).lower() and 'error' in str(x).lower() for x in app.log_history)


def test_check_activation_status_and_request_ticket(monkeypatch):
    monkeypatch.setattr(JarvisApp, '__init__', _fake_init_extended)
    app = JarvisApp()

    # check_activation_status without udid -> warning
    called = {}
    monkeypatch.setattr(main.messagebox, 'showwarning', lambda *a, **k: called.update({'warn': True}))
    app.check_activation_status()
    assert called.get('warn')

    # with udid -> backend called and messagebox.showinfo triggered
    app.current_udid = 'UD1'
    monkeypatch.setattr(bm, 'get_activation_status', lambda udid: {'activation_state': 'Activated', 'activation_lock': True, 'raw': 'xyz'})
    # ensure scheduled callbacks run synchronously in this test
    app.after = lambda ms, fn=None: fn()
    monkeypatch.setattr(threading, 'Thread', type('T', (), {'__init__': lambda s, target, daemon=True: setattr(s, '_t', target), 'start': lambda s: s._t() }))
    info_called = {}
    monkeypatch.setattr(main.messagebox, 'showinfo', lambda *a, **k: info_called.update({'info': True}))
    app.check_activation_status()
    assert info_called.get('info') is True

    # request_activation_ticket: when current_udid None -> warning
    called = {}
    monkeypatch.setattr(main.messagebox, 'showwarning', lambda *a, **k: called.update({'warn2': True}))
    app.current_udid = None
    app.request_activation_ticket()
    assert called.get('warn2')

    # with udid -> backend returns raw and server_text updated
    app.current_udid = 'UD2'
    monkeypatch.setattr(bm, 'request_activation_ticket', lambda udid: '<xml>OK</xml>')
    # ensure threading executes synchronously
    monkeypatch.setattr(threading, 'Thread', type('T2', (), {'__init__': lambda s, target, daemon=True: setattr(s, '_t', target), 'start': lambda s: s._t() }))
    app.request_activation_ticket()
    assert '<xml>OK' in app.server_text.get('1.0', 'end')


def test_open_captive_portal_handles_no_ip(monkeypatch):
    monkeypatch.setattr(JarvisApp, '__init__', _fake_init_extended)
    app = JarvisApp()
    monkeypatch.setattr(JarvisApp, '_get_local_ip', lambda s: None)
    called = {}
    monkeypatch.setattr(main.messagebox, 'showerror', lambda *a, **k: called.update({'err': True}))
    app.open_captive_portal()
    assert called.get('err')

    # when IP present, ensure clipboard and webbrowser used (monkeypatch both)
    monkeypatch.setattr(JarvisApp, '_get_local_ip', lambda s: '127.0.0.1')
    monkeypatch.setattr(webbrowser, 'open', lambda u: called.update({'open': u}))
    # monkeypatch CTkToplevel and CTkLabel to avoid real GUI creation
    class DummyPopup:
        def __init__(self, *a, **k):
            pass
        def title(self, *a, **k):
            pass
        def geometry(self, *a, **k):
            pass
        def destroy(self):
            pass
    class DummyLabel:
        def __init__(self, *a, **k):
            pass
        def pack(self, *a, **k):
            pass
    monkeypatch.setattr(main.ctk, 'CTkToplevel', DummyPopup)
    monkeypatch.setattr(main.ctk, 'CTkLabel', DummyLabel)
    # also stub CTkButton to avoid tkinter internals
    class DummyButton:
        def __init__(self, *a, **k):
            pass
        def pack(self, *a, **k):
            pass
    monkeypatch.setattr(main.ctk, 'CTkButton', DummyButton)
    # clipboard operations may raise; ensure no exception
    app.open_captive_portal()
    assert 'open' in called
