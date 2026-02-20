import io
import os
import json
import pytest
import importlib

if importlib.util.find_spec('flask') is None:
    pytest.skip('Flask not installed in test environment — skipping endpoint smoke tests', allow_module_level=True)

import portal_server as ps


def test_index_serves_portal_html():
    c = ps.app.test_client()
    r = c.get('/')
    assert r.status_code == 200
    assert b"captive" in r.get_data() or r.content_type.startswith('text/html')


def test_profile_mobileconfig_returns_attachment():
    c = ps.app.test_client()
    r = c.get('/profile.mobileconfig')
    assert r.status_code == 200
    assert r.content_type == 'application/x-apple-aspen-config'
    cd = r.headers.get('Content-Disposition', '')
    assert 'attachment' in cd and cd.endswith('.mobileconfig"')


def test_qr_png_returns_image():
    c = ps.app.test_client()
    r = c.get('/qr.png')
    assert r.status_code == 200
    assert r.content_type == 'image/png'
    assert len(r.get_data()) > 100


def test_signing_status_endpoint():
    c = ps.app.test_client()
    r = c.get('/signing-status')
    assert r.status_code == 200
    j = r.get_json()
    assert 'ok' in j and isinstance(j['ok'], bool)
    assert 'available' in j and 'enabled' in j


def test_generate_ssl_and_serve_cert_if_crypto_available(tmp_path):
    c = ps.app.test_client()
    # if cryptography is not available, endpoint should return an error
    if not hasattr(ps, 'CRYPTO_AVAILABLE') or not ps.CRYPTO_AVAILABLE:
        r = c.post('/generate-ssl')
        assert r.status_code != 200
        return

    # remove any old certs
    for p in (ps.SERVER_CERT, ps.SERVER_KEY, ps.PROFILE_CERT, ps.PROFILE_KEY):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    r = c.post('/generate-ssl')
    assert r.status_code == 200
    j = r.get_json()
    assert j.get('ok') is True
    assert os.path.exists(j['server_cert']) and os.path.exists(j['server_key'])

    # serve the server certificate via /certs/<name>
    name = os.path.basename(j['server_cert'])
    r2 = c.get(f'/certs/{name}')
    assert r2.status_code == 200
    assert b'-----BEGIN CERTIFICATE-----' in r2.get_data()


def test_recovery_kit_md_generates_file():
    c = ps.app.test_client()
    payload = {'device': {'model': 'iPhoneTest', 'serial': 'S123'}, 'requester': 'QA', 'format': 'md'}
    r = c.post('/recovery-kit', json=payload)
    # should return the generated file as attachment (200)
    assert r.status_code == 200
    cd = r.headers.get('Content-Disposition','')
    assert 'attachment' in cd and 'recovery_kit_' in cd


def test_upload_recovery_accepts_file(tmp_path):
    c = ps.app.test_client()
    data = {'file': (io.BytesIO(b'PDFDATA'), 'proof.pdf')}
    r = c.post('/upload-recovery', content_type='multipart/form-data', data=data)
    assert r.status_code == 200
    j = r.get_json()
    assert j.get('ok') is True
    assert 'url' in j


def test_activation_log_and_reload_permissions():
    c = ps.app.test_client()
    r = c.post('/activation-log', data='hello')
    assert r.status_code == 200
    assert r.get_json().get('ok') is True

    # reload should be allowed from localhost
    r2 = c.post('/reload')
    assert r2.status_code == 200
    assert r2.get_json().get('ok') is True

    # reload should be forbidden from remote addr
    r3 = c.post('/reload', environ_base={'REMOTE_ADDR': '10.0.0.5'})
    assert r3.status_code == 403

