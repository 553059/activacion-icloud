import os
import io
import json
import tempfile
import portal_server as ps
import profile_generator as pg


def test_profile_mobileconfig_signing_unavailable():
    c = ps.app.test_client()
    # ensure PROFILE_CERT/KEY do not exist
    monkey_cert = ps.PROFILE_CERT
    monkey_key = ps.PROFILE_KEY
    try:
        if os.path.exists(monkey_cert):
            os.remove(monkey_cert)
        if os.path.exists(monkey_key):
            os.remove(monkey_key)
    except Exception:
        pass

    r = c.get('/profile.mobileconfig?sign=1')
    assert r.status_code == 503
    j = r.get_json()
    assert j.get('error') == 'signing-unavailable'


def test_profile_mobileconfig_signing_path(monkeypatch, tmp_path):
    c = ps.app.test_client()
    # create dummy cert/key files and point module variables to them
    cert = tmp_path / 'profile_cert.pem'
    key = tmp_path / 'profile_key.pem'
    cert.write_bytes(b'cert')
    key.write_bytes(b'key')
    monkeypatch.setattr(ps, 'PROFILE_CERT', str(cert))
    monkeypatch.setattr(ps, 'PROFILE_KEY', str(key))
    # monkeypatch signer to return deterministic bytes
    monkeypatch.setattr(ps, 'sign_profile_with_openssl', lambda data, a, b: b'SIGNED')

    r = c.get('/profile.mobileconfig?sign=1')
    assert r.status_code == 200
    assert r.get_data() == b'SIGNED'
    cd = r.headers.get('Content-Disposition','')
    assert 'signed.mobileconfig' in cd


def test_device_status_and_set_signing(monkeypatch, tmp_path):
    c = ps.app.test_client()
    # missing udid -> 400
    r = c.get('/device-status')
    assert r.status_code == 400

    # successful status
    monkeypatch.setattr(ps, 'get_activation_status', lambda udid: {'activation_state': 'Activated', 'activation_lock': True, 'raw': 'x'})
    r2 = c.get('/device-status?udid=U1')
    assert r2.status_code == 200
    j = r2.get_json()
    assert j['ok'] is True and 'status' in j

    # set-signing: when profile cert missing and enabling -> error 400
    monkeypatch.setattr(ps, 'PROFILE_CERT', '/non/existent/cert.pem')
    monkeypatch.setattr(ps, 'PROFILE_KEY', '/non/existent/key.pem')
    r3 = c.post('/set-signing', json={'enabled': True})
    assert r3.status_code == 400

    # when certs exist, toggling should succeed and persist to SETTINGS_PATH (use tmp)
    tmp_settings = tmp_path / 'server_state.json'
    monkeypatch.setattr(ps, 'SETTINGS_PATH', str(tmp_settings))
    # create fake certs and point module vars
    cert2 = tmp_path / 'c.pem'
    key2 = tmp_path / 'k.pem'
    cert2.write_bytes(b'1')
    key2.write_bytes(b'2')
    monkeypatch.setattr(ps, 'PROFILE_CERT', str(cert2))
    monkeypatch.setattr(ps, 'PROFILE_KEY', str(key2))
    r4 = c.post('/set-signing', json={'enabled': True})
    assert r4.status_code == 200
    j4 = r4.get_json()
    assert j4.get('enabled') is True
    # verify persisted
    with open(str(tmp_settings), 'r', encoding='utf-8') as fh:
        obj = json.load(fh)
    assert obj.get('default_signing') is True
