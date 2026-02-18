import os
import time
import sys
import pytest
import backend_modules as bm
from main import JarvisApp


@pytest.mark.skipif(sys.platform.startswith("linux") and os.environ.get("CI") == "true", reason="Headless CI - skipping GUI test")
def test_gui_update_device_panel(tmp_path, monkeypatch):
    # prevent background poll_device from blocking by mocking backend device calls
    monkeypatch.setattr(bm, "list_devices", lambda: [])
    monkeypatch.setattr(bm, "get_device_info", lambda udid: {})

    # create app instance (no mainloop)
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
        # destroy GUI to free resources
        app.destroy()
