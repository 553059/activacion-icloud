import traceback
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import main
from main import JarvisApp

# minimal fake init (same as tests)
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

class _SimpleTextbox:
    def __init__(self, text=""):
        self._buf = text
        self._state = 'normal'
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

import queue

def _fake_init(self):
    self.device_info_text = _SimpleLabel()
    self.device_status_label = _SimpleLabel()
    self.dashboard_detail = _SimpleTextbox()
    self.console = _SimpleTextbox()
    self.log_history = []
    self.log_queue = queue.Queue()
    self.server_text = _SimpleTextbox()
    self.current_udid = None
    self.after = lambda *a, **k: None
    self.filter_info_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_warn_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_error_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_device_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_owner_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_panics_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_server_var = type('V',(object,),{'get': lambda s: True})()
    self.filter_text_var = type('V',(object,),{'get': lambda s: ''})()

JarvisApp.__init__ = _fake_init
app = JarvisApp()
# stub clipboard functions (headless)
app.clipboard_clear = lambda: None
app.clipboard_append = lambda v: None
# instance-level stub should accept no args
app._get_local_ip = lambda: '127.0.0.1'

print('Calling open_captive_portal() — will print traceback if it raises')
try:
    app.open_captive_portal()
    print('open_captive_portal() returned normally')
except Exception:
    traceback.print_exc()
    raise

print('\nLog history entries:')
for e in app.log_history[-10:]:
    print('-', e)
