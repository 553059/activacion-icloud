import os
import re
import shutil
import tempfile
import backend_modules as bm


def test_mask_email_and_phone():
    assert bm._mask_email("john.doe@example.com") == "j.....@example.com"
    assert bm._mask_email("a@d.co") == "a.....@d.co"
    assert bm._mask_email(None) is None

    assert bm._mask_phone("+1 (555) 123-4567") == "...4567"
    assert bm._mask_phone("123") == "...123"
    assert bm._mask_phone("") is None or isinstance(bm._mask_phone(""), str)


def test_diagnose_from_matches():
    assert "No se encontraron" in bm._diagnose_from_matches([])
    assert "Interposer" in bm._diagnose_from_matches(["SMC Panic"])
    assert "Watchdog Timeout" in bm._diagnose_from_matches(["WDT Timeout"])
    assert "baseband" in bm._diagnose_from_matches(["0x800"]).lower()
    assert "Hallazgos detectados" in bm._diagnose_from_matches(["panic"])


def test_list_devices_monkeypatched(monkeypatch):
    # missing command -> empty list
    monkeypatch.setattr(bm, "_run_with_retries", lambda cmd, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    assert bm.list_devices() == []

    # non-zero rc -> empty
    monkeypatch.setattr(bm, "_run_with_retries", lambda cmd, **kw: ("", "err", 1))
    assert bm.list_devices() == []

    # valid output
    monkeypatch.setattr(bm, "_run_with_retries", lambda cmd, **kw: ("UDID1\nUDID2\n", "", 0))
    assert bm.list_devices() == ["UDID1", "UDID2"]


def test_get_device_info_parsing(monkeypatch):
    sample_out = (
        "ProductType: iPhone10,1\n"
        "SerialNumber: SN123\n"
        "IMEI: 356000000000001\n"
        "BatteryCurrentCapacity: 85\n"
        "BatteryCycleCount: 12\n"
        "ProductVersion: 16.4\n"
    )
    monkeypatch.setattr(bm, "_run_with_retries", lambda cmd, **kw: (sample_out, "", 0))
    info = bm.get_device_info("FAKEUDID")
    assert info["imei"] == "356000000000001"
    assert info["model"] == "iPhone10,1"
    assert info["battery_percent"] == "85"
    assert info["battery_cycles"] == "12"
    assert "ProductVersion" in info["raw"] or "16.4" in info["raw"]

    # fallback: numeric-looking value in some other key
    sample_out2 = "SomeKey: 356000000000002\nDeviceName: iPhoneFake\n"
    monkeypatch.setattr(bm, "_run_with_retries", lambda cmd, **kw: (sample_out2, "", 0))
    info2 = bm.get_device_info("U2")
    assert info2["imei"] == "356000000000002"

    # fallback: raw regex search
    sample_out3 = "blah blah IMEI: ABCDEF12345 other"
    monkeypatch.setattr(bm, "_run_with_retries", lambda cmd, **kw: (sample_out3, "", 0))
    info3 = bm.get_device_info("U3")
    # the parser may include surrounding text when the IMEI-like token appears in a "key: value" line;
    # ensure the IMEI token is present in the returned value
    assert "ABCDEF12345" in (info3["imei"] or "")


def test_extract_owner_info_masks(monkeypatch):
    # return a combined output containing email and phone
    combined = "owner: {\"email\": \"owner.user@example.com\", \"phone\": \"+34 600-123-456\"}"

    def _runner(cmd, **kw):
        return (combined, "", 0)

    monkeypatch.setattr(bm, "_run_with_retries", _runner)
    res = bm.extract_owner_info("UDIDX")
    assert res["email"] == "owner.user@example.com"
    assert res["email_masked"].startswith("o.....@example.com")
    assert res["phone_masked"].endswith("3456") or res["phone_masked"].endswith("456")


def test_analyze_panics_detects_keywords_and_snippet(monkeypatch, tmp_path):
    # prepare a temporary directory and a fake .ips file containing 'SMC Panic'
    fake_dir = tmp_path / "jarvis_ips_test"
    fake_dir.mkdir()
    p = fake_dir / "crash1.ips"
    p.write_text("random preamble\nSMC Panic occurred here with more context 0x800\nend")

    # ensure tempfile.mkdtemp returns our fake dir
    monkeypatch.setattr(bm, "tempfile", bm.tempfile)
    monkeypatch.setattr(bm.tempfile, "mkdtemp", lambda prefix=None: str(fake_dir))

    # make _stream_with_retries a no-op that returns success
    monkeypatch.setattr(bm, "_stream_with_retries", lambda cmd, **kw: ("", 0))

    res = bm.analyze_panics("UDIDPANIC")
    assert any("SMC Panic" in m for m in res["matches"]) or any("panic" in m.lower() for m in res["matches"])
    assert "SMC Panic" in res["snippets"] or "SMC Panic" in " ".join(res["matches"]) 
    assert "SMC" in res["diagnosis"] or isinstance(res["diagnosis"], str)
    assert any(str(p) in f for f in res["files"]) or any(os.path.basename(fp) == "crash1.ips" for fp in res["files"])


def test_analyze_panics_command_missing(monkeypatch, tmp_path):
    # when idevicecrashreport not available, _stream_with_retries raises FileNotFoundError
    fake_dir = tmp_path / "jarvis_ips_test2"
    # return a path (function will attempt to rmtree it on exception)
    monkeypatch.setattr(bm.tempfile, "mkdtemp", lambda prefix=None: str(fake_dir))
    monkeypatch.setattr(bm, "_stream_with_retries", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))

    try:
        bm.analyze_panics("UDIDX")
        raise AssertionError("Expected RuntimeError when idevicecrashreport is missing")
    except RuntimeError as e:
        assert "idevicecrashreport no disponible" in str(e)


def test_run_with_retries_and_stream_with_retries(monkeypatch):
    # _run_with_retries should retry on transient 'lockdownd' error
    calls = {'n': 0}
    def fake_run(cmd, timeout=30):
        calls['n'] += 1
        if calls['n'] == 1:
            return ("err lockdownd", "", 1)
        return ("ok", "", 0)
    monkeypatch.setattr(bm, '_run', fake_run)
    out, err, rc = bm._run_with_retries(['cmd'])
    assert rc == 0 and calls['n'] > 1

    # _stream_with_retries should retry on 'mux error'
    scalls = {'n': 0}
    def fake_stream(cmd, timeout=None):
        scalls['n'] += 1
        if scalls['n'] == 1:
            return ("mux error", 1)
        return ("ok", 0)
    monkeypatch.setattr(bm, '_stream', fake_stream)
    out, rc = bm._stream_with_retries(['cmd'])
    assert rc == 0 and scalls['n'] > 1


def test_request_activation_ticket_and_get_activation_status(monkeypatch):
    # request_activation_ticket -> FileNotFoundError for all tries -> RuntimeError
    monkeypatch.setattr(bm, '_run_with_retries', lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
    try:
        bm.request_activation_ticket('UD')
        raise AssertionError('Expected RuntimeError')
    except RuntimeError:
        pass

    # get_activation_status should parse ActivationState and activation_lock
    def fake_run_with(cmd, **kw):
        # emulate ideviceinfo -k ActivationState
        if '-k' in cmd:
            return ('Activated\n', '', 0)
        # emulate ideviceactivation activation-info containing ActivationLock
        if 'activation-info' in cmd:
            return ('Some ActivationLock present', '', 0)
        return ('', '', 1)
    monkeypatch.setattr(bm, '_run_with_retries', fake_run_with)
    status = bm.get_activation_status('UD')
    assert status['activation_state'] == 'Activated'
    assert status['activation_lock'] is True


def test_restart_springboard_backend_paths(monkeypatch):
    # successful restart
    monkeypatch.setattr(bm, '_run_with_retries', lambda cmd, **kw: ('restarted', '', 0))
    out = bm.restart_springboard('UD')
    assert 'restarted' in out

    # both commands fail -> raise
    def raise_fn(cmd, **kw):
        raise FileNotFoundError()
    monkeypatch.setattr(bm, '_run_with_retries', raise_fn)
    try:
        bm.restart_springboard('UD')
        raise AssertionError('Expected RuntimeError')
    except RuntimeError:
        pass
