import os
import json
import tempfile
import shutil
import importlib
import pytest

if importlib.util.find_spec('flask') is None:
    pytest.skip('Flask not installed in test environment — skipping portal signing tests', allow_module_level=True)

import portal_server as ps


def test_signing_status_unavailable(tmp_path):
    client = ps.app.test_client()
    # ensure profile cert/key are not present
    try:
        if os.path.exists(ps.PROFILE_CERT):
            os.remove(ps.PROFILE_CERT)
        if os.path.exists(ps.PROFILE_KEY):
            os.remove(ps.PROFILE_KEY)
    except Exception:
        pass
    r = client.get('/signing-status')
    assert r.status_code == 200
    j = r.get_json()
    assert j['ok'] is True
    assert j['available'] is False
    # default signing should be boolean
    assert isinstance(j['enabled'], bool)


def test_set_signing_unavailable(tmp_path):
    client = ps.app.test_client()
    # ensure certs absent
    try:
        if os.path.exists(ps.PROFILE_CERT):
            os.remove(ps.PROFILE_CERT)
        if os.path.exists(ps.PROFILE_KEY):
            os.remove(ps.PROFILE_KEY)
    except Exception:
        pass
    r = client.post('/set-signing', json={'enabled': True})
    assert r.status_code == 400
    j = r.get_json()
    assert j.get('error') == 'signing-unavailable'


def test_set_signing_available_and_toggle(tmp_path):
    client = ps.app.test_client()
    # create dummy cert/key files to simulate availability
    os.makedirs(ps.CERTS_DIR, exist_ok=True)
    with open(ps.PROFILE_CERT, 'w', encoding='utf-8') as f:
        f.write('---DUMMY CERT---')
    with open(ps.PROFILE_KEY, 'w', encoding='utf-8') as f:
        f.write('---DUMMY KEY---')
    # enable signing
    r = client.post('/set-signing', json={'enabled': True})
    assert r.status_code == 200
    j = r.get_json()
    assert j['ok'] is True
    assert j['enabled'] is True
    # status should reflect enabled and available
    r2 = client.get('/signing-status')
    j2 = r2.get_json()
    assert j2['available'] is True
    assert j2['enabled'] is True
    # disable signing
    r3 = client.post('/set-signing', json={'enabled': False})
    j3 = r3.get_json()
    assert j3['ok'] is True
    assert j3['enabled'] is False
    # cleanup
    try:
        os.remove(ps.PROFILE_CERT)
        os.remove(ps.PROFILE_KEY)
        if os.path.exists(ps.SETTINGS_PATH):
            os.remove(ps.SETTINGS_PATH)
    except Exception:
        pass
