import types
import os
import tempfile
import subprocess
import backend_modules as bm


def test_list_devices_monkeypatch(monkeypatch):
    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        return types.SimpleNamespace(stdout="TESTUDID123\n", stderr="", returncode=0)
    monkeypatch.setattr(bm, "subprocess", types.SimpleNamespace(run=fake_run))
    devices = bm.list_devices()
    assert devices == ["TESTUDID123"]


def test_get_device_info_parsing(monkeypatch):
    sample = (
        "ProductType: iPhone8,1\n"
        "SerialNumber: ABCDEF123\n"
        "IMEI: 356789012345678\n"
        "BatteryCurrentCapacity: 87\n"
        "BatteryCycleCount: 112\n"
        "ProductVersion: 14.4\n"
    )

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        return types.SimpleNamespace(stdout=sample, stderr="", returncode=0)

    monkeypatch.setattr(bm, "subprocess", types.SimpleNamespace(run=fake_run))
    info = bm.get_device_info("UDID-1")
    assert info["model"] == "iPhone8,1"
    assert info["serial"] == "ABCDEF123"
    assert info["imei"] == "356789012345678"
    assert info["battery_percent"] == "87"
    assert info["battery_cycles"] == "112"
    assert info["ios_version"] == "14.4"


def test_get_device_info_avoids_timeinterval_trap(monkeypatch):
    # ensure that keys like TimeIntervalSince1970 don't get picked as IMEI
    sample = (
        "ProductType: iPhone8,1\n"
        "SerialNumber: ABCDEF123\n"
        "TimeIntervalSince1970: 1771474332.9144621\n"
        "InternationalMobileEquipmentIdentity: 352033764956566\n"
        "ProductVersion: 14.4\n"
    )

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        return types.SimpleNamespace(stdout=sample, stderr="", returncode=0)

    monkeypatch.setattr(bm, "subprocess", types.SimpleNamespace(run=fake_run))
    info = bm.get_device_info("UDID-T")
    assert info["imei"] == "352033764956566"



def test_extract_owner_info_masks(monkeypatch):
    sample = "OwnerEmail: owner@example.com\nOwnerPhone: +1 555 987 1234\n"

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        return types.SimpleNamespace(stdout=sample, stderr="", returncode=0)

    monkeypatch.setattr(bm, "subprocess", types.SimpleNamespace(run=fake_run))
    res = bm.extract_owner_info("UDID-2")
    assert res["email"] == "owner@example.com"
    assert res["email_masked"].startswith("o.....@")
    assert res["phone_masked"].endswith("1234")


def test_request_activation_ticket(monkeypatch):
    sample = "<plist>\nActivationState: Clean\n</plist>"

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        return (sample, "", 0)

    monkeypatch.setattr(bm, "_run", fake_run)
    out = bm.request_activation_ticket("UDID-3")
    assert "ActivationState" in out


def test_restart_springboard_uses_run(monkeypatch):
    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        return ("restarting", "", 0)
    monkeypatch.setattr(bm, "_run", fake_run)
    out = bm.restart_springboard("UDID-4")
    assert "restarting" in out


def test_analyze_panics_reads_files(tmp_path, monkeypatch):
    # prepare fake ips file containing a keyword
    p = tmp_path / "sample.ips"
    p.write_text("Some header\nSMC Panic detected in hardware\nfooter")

    # make mkdtemp return this tmp_path
    monkeypatch.setattr(bm, "tempfile", types.SimpleNamespace(mkdtemp=lambda prefix=None: str(tmp_path)))

    # mock _stream to do nothing (simulate successful idevicecrashreport)
    monkeypatch.setattr(bm, "_stream", lambda cmd, timeout=None: ("", 0))

    res = bm.analyze_panics("UDID-5")
    assert any("SMC Panic" in m for m in res["matches"]) or "panic" in " ".join(res["matches"]).lower()
    assert str(p) in res["files"]


def test__run_timeout_propagates(monkeypatch):
    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        raise subprocess.TimeoutExpired(cmd, timeout)
    monkeypatch.setattr(bm, "subprocess", types.SimpleNamespace(run=fake_run))
    import pytest
    with pytest.raises(subprocess.TimeoutExpired):
        bm._run(["sleep", "1"], timeout=0.001)


def test_list_devices_handles_nonzero_rc(monkeypatch):
    monkeypatch.setattr(bm, "_run", lambda cmd, timeout=5: ("", "err", 1))
    assert bm.list_devices() == []


def test_get_device_info_raises_on_nonzero(monkeypatch):
    monkeypatch.setattr(bm, "_run", lambda cmd, timeout=8: ("", "err", 1))
    import pytest
    with pytest.raises(RuntimeError):
        bm.get_device_info("UDID-X")


def test_list_devices_handles_missing_tool(monkeypatch):
    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        raise FileNotFoundError
    monkeypatch.setattr(bm, "subprocess", types.SimpleNamespace(run=fake_run))
    assert bm.list_devices() == []


def test_perform_activation_writes_and_runs(monkeypatch, tmp_path):
    """perform_activation debe escribir el ticket y ejecutar ideviceactivation; en éxito devuelve la salida."""
    sample_ticket = "<xml>ticket</xml>"
    # simular que _run_with_retries devuelve rc==0
    monkeypatch.setattr(bm, "_run_with_retries", lambda cmd, timeout=30, retries=2: ("OK", "", 0))
    out = bm.perform_activation("UD-ACT", sample_ticket)
    assert "OK" in out
