"""
scripts/verify_setup.py

Verificador automático del entorno y portal de Jarvis.

Comprueba:
 - dependencias Python (imports)
 - herramientas externas (openssl, idevice*)
 - servidor `portal_server.py` (arranca si no está activo)
 - endpoints principales (/, /signing-status, /profile.mobileconfig, /qr.png, /recovery-kit)
 - firma de mobileconfig cuando OpenSSL está disponible
 - ejecución del script headless `scripts/press_buttons_headless.py`

Uso:
    python scripts/verify_setup.py
    python scripts/verify_setup.py --run-tests    # opcional: lanza un conjunto reducido de pytest

Salida: resumen legible y código de salida != 0 si hay fallos críticos.

Este script es seguro: no realiza cambios destructivos en dispositivos.
"""
from __future__ import annotations
import os
import sys
import time
import shutil
import subprocess
import socket
import argparse

try:
    import requests
    from requests.exceptions import RequestException
except Exception:
    requests = None

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CERT_PATH = os.path.join(ROOT, 'certs', 'server.crt')


def which(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def server_is_up(base_url: str, verify: bool) -> bool:
    if requests is None:
        return False
    try:
        r = requests.get(f"{base_url}/signing-status", verify=verify, timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False


def find_base_url() -> tuple[str, bool]:
    # prefer https when cert exists
    if os.path.exists(CERT_PATH):
        return ('https://127.0.0.1:5000', False)
    return ('http://127.0.0.1:5000', True)


def start_portal_if_needed() -> tuple[bool, subprocess.Popen | None]:
    base, verify = find_base_url()
    if server_is_up(base, verify):
        print(f"[INFO] portal already running at {base}")
        return (False, None)

    print('[INFO] starting portal_server.py in background...')
    env = os.environ.copy()
    p = subprocess.Popen([sys.executable, os.path.join(ROOT, 'portal_server.py')], cwd=ROOT,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # wait for it to become available
    deadline = time.time() + 15.0
    while time.time() < deadline:
        if server_is_up(base, verify):
            print(f"[OK] portal responding at {base}")
            return (True, p)
        time.sleep(0.3)
    # timeout -> collect logs
    print('[ERROR] portal did not start within timeout. Collecting last stdout/stderr...')
    try:
        out = p.stdout.read() if p.stdout else ''
        err = p.stderr.read() if p.stderr else ''
        print('--- portal stdout ---')
        print(out[-400:])
        print('--- portal stderr ---')
        print(err[-400:])
    except Exception:
        pass
    p.kill()
    return (True, None)


def stop_portal(proc: subprocess.Popen | None) -> None:
    if not proc:
        return
    try:
        proc.terminate()
        proc.wait(timeout=4)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def http_get(base: str, path: str, verify: bool = False, expect_code: int = 200, method: str = 'get', **kwargs) -> tuple[bool, requests.Response | None]:
    if requests is None:
        return (False, None)
    url = base + path
    try:
        r = getattr(requests, method)(url, timeout=5, verify=verify, **kwargs)
        ok = (r.status_code == expect_code)
        return (ok, r)
    except RequestException as e:
        print(f"[ERROR] request {url} failed: {e}")
        return (False, None)


def run_headless() -> bool:
    print('[INFO] running headless smoke (`scripts/press_buttons_headless.py`)')
    cmd = [sys.executable, os.path.join(ROOT, 'scripts', 'press_buttons_headless.py')]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    print('--- headless stdout (tail 200 chars) ---')
    print(r.stdout[-200:])
    if r.stderr:
        print('--- headless stderr (tail 200 chars) ---')
        print(r.stderr[-200:])
    return r.returncode == 0


def run_selected_pytests() -> bool:
    print('[INFO] running a small set of pytest smoke tests')
    cmd = [sys.executable, '-m', 'pytest', '-q', 'tests/test_backend_subprocess.py::test_perform_activation_writes_and_runs', 'tests/test_main_additional.py::test_activate_device_requests_ticket_and_runs']
    r = subprocess.run(cmd, cwd=ROOT)
    return r.returncode == 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-tests', action='store_true', help='Run a small subset of pytest after checks')
    args = parser.parse_args(argv)

    failures = []
    warnings = []

    print('\n=== Environment checks ===')
    print('Python executable:', sys.executable)
    print('Repo root:', ROOT)

    # requests availability
    if requests is None:
        failures.append('requests library is not importable. Run `pip install -r requirements.txt`.')
    else:
        print('[OK] requests importable')

    # external commands
    print('\n=== External commands ===')
    for c in ('openssl', 'ideviceinfo', 'ideviceactivation', 'idevicediagnostics', 'idevicecrashreport'):
        found = which(c)
        print(f"{c}: {'FOUND' if found else 'missing'}")
        if not found and c.startswith('idevice'):
            warnings.append(f"{c} not found — device-related features will be unavailable")

    # portal server
    print('\n=== Portal / server checks ===')
    base, verify = find_base_url()
    started, proc = start_portal_if_needed()
    if proc is None and not server_is_up(base, verify):
        failures.append('Could not start or contact portal_server')
    else:
        # run HTTP checks
        ok, r = http_get(base, '/', verify=verify, expect_code=200)
        print(f"GET / -> {'OK' if ok else 'FAIL'}")
        ok, st = http_get(base, '/signing-status', verify=verify, expect_code=200)
        if not ok:
            failures.append('/signing-status failed')
        else:
            js = st.json()
            print('signing-status ->', js)

        # profile (unsigned)
        ok, r = http_get(base, '/profile.mobileconfig?ssid=VerifyNet&dns=1.1.1.1&sign=0', verify=verify)
        print(f"GET /profile.mobileconfig?sign=0 -> {'OK' if ok else 'FAIL'} (len={len(r.content) if r else 'n/a'})")

        # try to enable server-side signing if available
        # first generate ssl certs so profile cert exists
        ok_gen, gen_r = http_get(base, '/generate-ssl', verify=verify, expect_code=200, method='post')
        if not ok_gen:
            warnings.append('generate-ssl failed (cryptography may be missing)')
        else:
            print('[OK] generate-ssl')
            ok_set, set_r = http_get(base, '/set-signing', verify=verify, method='post', json={'enabled': True})
            print('POST /set-signing ->', OK(set_r) if (set_r := set_r) else 'n/a')

        # check signed profile behavior depending on OpenSSL availability
        openssl_ok = which('openssl')
        print('openssl in PATH:', openssl_ok)
        ok_signed, signed_r = http_get(base, '/profile.mobileconfig?ssid=VerifyNet&dns=1.1.1.1&sign=1', verify=verify)
        if openssl_ok:
            if not ok_signed:
                failures.append('Signed profile requested but failed (OpenSSL present)')
            else:
                # expect non-JSON response (DER binary)
                ct = signed_r.headers.get('Content-Type','')
                if 'application/json' in ct or signed_r.text.strip().startswith('{'):
                    failures.append('Signed profile returned JSON (unexpected)')
                else:
                    print('[OK] signed profile returned; Content-Type=', ct, 'len=', len(signed_r.content))
        else:
            # OpenSSL absent -> service may return 500; accept either informative 5xx or signing-unavailable
            if ok_signed:
                warnings.append('Server returned signed profile even though openssl missing locally — verify signature validity manually')
            else:
                print('[WARN] signed profile not available (openssl missing) — install OpenSSL to enable signing')

        # QR endpoint
        ok_qr, qr_r = http_get(base, '/qr.png?data=https://example.com', verify=verify)
        print('GET /qr.png ->', 'OK' if ok_qr else 'FAIL')

        # recovery-kit
        payload = {'device': {'serial': 'TEST123', 'model': 'iPhoneTest', 'os': '14.4'}, 'requester': 'Verify', 'format': 'pdf'}
        ok_rec, rec_r = http_get(base, '/recovery-kit', verify=verify, method='post', json=payload)
        print('POST /recovery-kit ->', 'OK' if ok_rec else 'FAIL')

        # device-status: missing udid -> expect 400
        ok_ds, ds_r = http_get(base, '/device-status', verify=verify, expect_code=400)
        print('GET /device-status (no udid) ->', 'OK' if ok_ds else 'FAIL')

    # run headless smoke
    print('\n=== Headless smoke tests ===')
    headless_ok = run_headless()
    if not headless_ok:
        failures.append('headless smoke script failed')

    # optional pytest subset
    if args.run_tests:
        print('\n=== pytest smoke subset ===')
        tests_ok = run_selected_pytests()
        if not tests_ok:
            failures.append('pytest smoke subset failed')

    # stop portal if we started it
    if started and proc:
        print('[INFO] stopping portal server started by this script...')
        stop_portal(proc)

    # summary
    print('\n=== SUMMARY ===')
    if failures:
        print('[FAILURES]')
        for f in failures:
            print('-', f)
    else:
        print('[OK] no critical failures detected')
    if warnings:
        print('\n[WARNINGS]')
        for w in warnings:
            print('-', w)

    return 1 if failures else 0


def OK(r):
    try:
        return r.json()
    except Exception:
        return str(r.status_code) if r is not None else 'n/a'


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
