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


def test_sign_profile_with_openssl_openssl_fails_but_fallback_works(monkeypatch, tmp_path):
    """Si OpenSSL falla en la llamada externa, debe usarse el fallback con `cryptography`.

    Simulamos fallo en subprocess.run y comprobamos que la llamada devuelve bytes (fallback activo).
    """
    # simulate openssl failing
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(args=[], returncode=1, stderr=b'bad'))

    # create a real cert/key pair so fallback can sign
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.x509 import NameOID
    from cryptography import x509
    import datetime

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Test')])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )

    cert_path = tmp_path / 'cert.pem'
    key_path = tmp_path / 'key.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ))

    signed = pg.sign_profile_with_openssl(b'ABC', str(cert_path), str(key_path))
    assert isinstance(signed, (bytes, bytearray)) and len(signed) > 0


def test_sign_profile_with_openssl_no_fallback_raises(monkeypatch):
    """Si OpenSSL falla y no hay cryptography, debe lanzarse RuntimeError."""
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(args=[], returncode=1, stderr=b'bad'))
    # simulate cryptography missing
    import sys
    monkeypatch.setitem(sys.modules, 'cryptography', None)
    try:
        import profile_generator as pg2
        try:
            pg2.sign_profile_with_openssl(b'abc', 'cert.pem', 'key.pem')
            raise AssertionError('Expected RuntimeError when no fallback available')
        except RuntimeError:
            pass
    finally:
        # restore possible side-effects (monkeypatch handles sys.modules restore automatically)
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
