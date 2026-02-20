#!/usr/bin/env python3
"""
scripts/portal_smoke.py

Script de comprobación automática para el portal cautivo:
- detecta URL (https/http) en 127.0.0.1 y en la IP local
- valida endpoints: /, /profile.mobileconfig, /qr.png, /generate-ssl, /certs/*, /recovery-kit, /upload-recovery, /signing-status, /set-signing, /activation-log
- opcional: /reload (no se ejecuta por defecto porque reinicia el servidor)

Salida: código 0 si todas las comprobaciones críticas pasan; !=0 si hay fallos.

Uso:
    python scripts/portal_smoke.py [--host <IP>] [--port 5000] [--skip-reload] [--trust-cert]

"""
from __future__ import annotations
import argparse
import requests
import socket
import sys
import time
import tempfile
import os


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def try_urls(host, port):
    candidates = []
    # prefer https
    candidates.append((f"https://{host}:{port}", False))
    ip = local_ip()
    if ip and ip != host:
        candidates.append((f"https://{ip}:{port}", False))
    candidates.append((f"http://{host}:{port}", True))
    if ip and ip != host:
        candidates.append((f"http://{ip}:{port}", True))
    return candidates


def check_root(base, verify):
    url = base + '/'
    r = requests.get(url, timeout=4, verify=verify)
    ok = r.status_code == 200 and ('text/html' in r.headers.get('Content-Type', ''))
    return ok, r


def check_profile(base, verify, sign=False):
    url = base + f"/profile.mobileconfig" + ("?sign=1" if sign else "")
    r = requests.get(url, timeout=6, verify=verify, allow_redirects=True)
    return r.status_code, r.headers.get('Content-Type',''), r.content[:64]


def check_qr(base, verify):
    r = requests.get(base + '/qr.png', timeout=4, verify=verify)
    return r.status_code == 200 and r.headers.get('Content-Type','').startswith('image/') and len(r.content) > 100


def post_generate_ssl(base, verify):
    r = requests.post(base + '/generate-ssl', timeout=6, verify=verify)
    return r.status_code, r


def fetch_cert(base, verify):
    r = requests.get(base + '/certs/server.crt', timeout=6, verify=verify)
    if r.status_code == 200 and b'BEGIN CERTIFICATE' in r.content:
        fd, path = tempfile.mkstemp(suffix='.crt')
        os.write(fd, r.content)
        os.close(fd)
        return True, path
    return False, None


def post_recovery_md(base, verify):
    payload = {'device': {'model': 'SmokePhone', 'serial': 'SMK123'}, 'requester': 'smoke', 'format': 'md'}
    r = requests.post(base + '/recovery-kit', json=payload, timeout=6, verify=verify)
    return r.status_code == 200, r


def upload_recovery(base, verify):
    files = {'file': ('proof.txt', b'proof')}
    r = requests.post(base + '/upload-recovery', files=files, timeout=6, verify=verify)
    try:
        j = r.json()
    except Exception:
        j = {}
    return r.status_code == 200 and j.get('ok') is True, j


def post_activation_log(base, verify):
    r = requests.post(base + '/activation-log', data='hello', timeout=4, verify=verify)
    try:
        j = r.json()
    except Exception:
        j = {}
    return r.status_code == 200 and j.get('ok') is True


def get_signing_status(base, verify):
    r = requests.get(base + '/signing-status', timeout=4, verify=verify)
    try:
        return r.status_code == 200, r.json()
    except Exception:
        return False, {}


def set_signing(base, verify, want):
    r = requests.post(base + '/set-signing', json={'enabled': want}, timeout=4, verify=verify)
    try:
        return r.status_code in (200, 400), r.json()
    except Exception:
        return False, {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=5000)
    ap.add_argument('--skip-reload', action='store_true')
    ap.add_argument('--trust-cert', action='store_true', help='Descargar cert localmente y usarlo para verificar TLS')
    args = ap.parse_args()

    host = args.host
    port = args.port
    candidates = try_urls(host, port)

    chosen = None
    chosen_verify = False
    downloaded_cert = None

    print('Portal smoke: probing endpoints...')
    for base, verify_hint in candidates:
        try:
            # when using https with self-signed, allow verify=False for probe
            r = requests.get(base + '/', timeout=2, verify=False)
            if r.status_code == 200:
                chosen = base
                # if base is https, we plan to use verify=False unless trust-cert specified
                chosen_verify = True if base.startswith('http://') else False
                break
        except Exception:
            continue

    if not chosen:
        print('ERROR: no reachable portal URL found among candidates:')
        for u, _ in candidates:
            print('  -', u)
        sys.exit(2)

    print('Using portal URL:', chosen)

    # optionally download server.crt and use for verification
    verify = False
    if args.trust_cert and chosen.startswith('https://'):
        ok, cert_path = fetch_cert(chosen, verify=False)
        if ok:
            downloaded_cert = cert_path
            verify = cert_path
            print('Downloaded server certificate to', cert_path)
        else:
            print('Could not download server.crt; proceeding with insecure verify')
    else:
        verify = False

    failures = []

    # check root
    try:
        ok, r = check_root(chosen, verify)
        print('  / ->', 'OK' if ok else f'FAIL (status {r.status_code if hasattr(r,"status_code") else r})')
        if not ok:
            failures.append('/ root failed')
    except Exception as e:
        failures.append(f'/ root exception: {e}')

    # profile
    try:
        sc, ctype, snippet = check_profile(chosen, verify, sign=False)
        print('  /profile.mobileconfig ->', sc, ctype)
        if sc != 200:
            failures.append('/profile.mobileconfig failed')
    except Exception as e:
        failures.append(f'/profile exception: {e}')

    # qr
    try:
        ok = check_qr(chosen, verify)
        print('  /qr.png ->', 'OK' if ok else 'FAIL')
        if not ok:
            failures.append('/qr.png failed')
    except Exception as e:
        failures.append(f'/qr exception: {e}')

    # signing status
    try:
        ok, js = get_signing_status(chosen, verify)
        print('  /signing-status ->', 'OK' if ok else 'FAIL', js if ok else '')
    except Exception as e:
        failures.append(f'/signing-status exception: {e}')
        js = {}

    # try to toggle signing only if available
    try:
        avail = js.get('available')
        if avail:
            ok, resp = set_signing(chosen, verify, True)
            print('  /set-signing enable ->', ok, resp)
            ok2, resp2 = set_signing(chosen, verify, False)
            print('  /set-signing disable ->', ok2, resp2)
        else:
            print('  /set-signing -> signing unavailable on server (skipped)')
    except Exception as e:
        failures.append(f'/set-signing exception: {e}')

    # generate-ssl (may be available or not)
    try:
        sc, r = post_generate_ssl(chosen, verify)
        print('  /generate-ssl ->', sc, r.text[:200])
        if sc not in (200, 500):
            failures.append('/generate-ssl unexpected status')
    except Exception as e:
        failures.append(f'/generate-ssl exception: {e}')

    # fetch server cert
    try:
        ok, p = fetch_cert(chosen, verify=False)
        print('  /certs/server.crt ->', 'OK' if ok else 'FAIL')
        if not ok:
            failures.append('/certs/server.crt failed')
        else:
            # cleanup after
            if p and os.path.exists(p):
                os.remove(p)
    except Exception as e:
        failures.append(f'/certs exception: {e}')

    # recovery kit generation (md)
    try:
        ok, resp = post_recovery_md(chosen, verify)
        print('  /recovery-kit (md) ->', 'OK' if ok else f'FAIL ({resp.status_code})')
        if not ok:
            failures.append('/recovery-kit failed')
    except Exception as e:
        failures.append(f'/recovery-kit exception: {e}')

    # upload recovery
    try:
        ok, j = upload_recovery(chosen, verify)
        print('  /upload-recovery ->', 'OK' if ok else 'FAIL', j)
        if not ok:
            failures.append('/upload-recovery failed')
    except Exception as e:
        failures.append(f'/upload-recovery exception: {e}')

    # activation-log
    try:
        ok = post_activation_log(chosen, verify)
        print('  /activation-log ->', 'OK' if ok else 'FAIL')
        if not ok:
            failures.append('/activation-log failed')
    except Exception as e:
        failures.append(f'/activation-log exception: {e}')

    # reload (skip by default)
    if not args.skip_reload:
        try:
            r = requests.post(chosen + '/reload', timeout=3, verify=verify)
            print('  /reload ->', r.status_code, r.text[:120])
            # server will restart; wait a bit
            time.sleep(1.2)
        except Exception as e:
            failures.append(f'/reload exception: {e}')
    else:
        print('  /reload -> skipped (use --skip-reload to enable)')

    print('\nSummary:')
    if failures:
        print(' FAIL - some checks failed:')
        for f in failures:
            print('  -', f)
        sys.exit(3)
    else:
        print(' ALL OK - portal health checks passed')
        sys.exit(0)


if __name__ == '__main__':
    main()
