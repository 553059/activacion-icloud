import os
import plistlib
import subprocess
import tempfile
import profile_generator as pg


def test_validate_dns_ok_and_bad():
    assert pg.MobileConfigBuilder._validate_dns(["1.1.1.1"]) == ["1.1.1.1"]
    assert pg.MobileConfigBuilder._validate_dns(["::1"]) == ["::1"]
    try:
        pg.MobileConfigBuilder._validate_dns(["not-an-ip"])
        raise AssertionError("Expected ValueError for invalid DNS")
    except ValueError:
        pass


def test_add_wifi_payload_and_as_bytes_contains_fields(tmp_path):
    b = pg.MobileConfigBuilder(display_name="TestProfile", identifier_base="com.test.profile")
    b.add_wifi_payload(ssid="MyNet", password="pw", encryption="WPA2", dns_servers=["1.1.1.1"])
    data = b.as_bytes()
    assert isinstance(data, (bytes, bytearray))
    parsed = plistlib.loads(data)
    assert parsed["PayloadDisplayName"] == "TestProfile"
    assert isinstance(parsed["PayloadContent"], list)
    p = parsed["PayloadContent"][0]
    assert p["SSID_STR"] == "MyNet"
    assert p["Password"] == "pw"
    assert p["DNSServerAddresses"] == ["1.1.1.1"]

    # test save
    outp = tmp_path / "out.mobileconfig"
    b.save(str(outp))
    assert outp.exists()
    with open(outp, 'rb') as fh:
        _ = plistlib.loads(fh.read())


def test_sign_profile_with_openssl_failure(monkeypatch):
    # simulate openssl failing
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(args=[], returncode=1, stderr=b'bad'))
    try:
        pg.sign_profile_with_openssl(b'abc', 'cert.pem', 'key.pem')
        raise AssertionError("Expected RuntimeError when OpenSSL fails")
    except RuntimeError:
        pass


def test_sign_and_verify_with_mock_success(monkeypatch):
    # mock subprocess.run to write the expected '-out' file and return success
    def _fake_run(cmd, capture_output=True):
        # find output path after '-out'
        out_path = None
        if '-out' in cmd:
            out_path = cmd[cmd.index('-out') + 1]
        elif '-out' in cmd:
            out_path = cmd[cmd.index('-out') + 1]
        if out_path:
            with open(out_path, 'wb') as fh:
                fh.write(b'SIGNED-BY-MOCK')
        return subprocess.CompletedProcess(args=cmd, returncode=0, stderr=b'')

    monkeypatch.setattr(subprocess, 'run', _fake_run)

    signed = pg.sign_profile_with_openssl(b'PLAIN', 'cert.pem', 'key.pem')
    assert signed == b'SIGNED-BY-MOCK'

    # verify returns True when openssl returns 0
    ok = pg.verify_signed_profile_with_openssl(signed, 'ca.pem')
    assert ok is True

    # simulate verify failing
    def _fake_run_fail(cmd, capture_output=True):
        return subprocess.CompletedProcess(args=cmd, returncode=2, stderr=b'err')
    monkeypatch.setattr(subprocess, 'run', _fake_run_fail)
    assert pg.verify_signed_profile_with_openssl(b'X', 'ca.pem') is False
