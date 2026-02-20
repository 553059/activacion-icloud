"""
portal_server.py

Servidor Flask ligero que sirve:
 - portal cautivo (UI)
 - endpoint para generación on‑the‑fly de .mobileconfig (profile_generator)
 - endpoint QR (dinámico)
 - endpoints de diagnóstico / recovery-kit

USO RÁPIDO:
  python -m venv .venv
  .venv/Scripts/activate
  pip install -r requirements.txt
  python portal_server.py

Luego abrir: http://<IP‑PC>:5000/

AVISO: Este servidor ofrece herramientas para DIAGNÓSTICO y recuperación legítima. No debe emplearse para eludir Activation Lock ni para actividades ilegales.
"""
from __future__ import annotations
import os
from flask import Flask, send_from_directory, request, jsonify, make_response, url_for
from flask_cors import CORS
from profile_generator import MobileConfigBuilder, sign_profile_with_openssl
import recovery_docs
import io
import qrcode
import time
import subprocess
from backend_modules import get_activation_status
# optional cryptography for generating self-signed server/profile certs
try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    CRYPTO_AVAILABLE = True
except Exception:
    CRYPTO_AVAILABLE = False

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
CERTS_DIR = os.path.join(os.path.dirname(__file__), 'certs')
os.makedirs(CERTS_DIR, exist_ok=True)
SERVER_CERT = os.path.join(CERTS_DIR, 'server.crt')
SERVER_KEY = os.path.join(CERTS_DIR, 'server.key')
PROFILE_CERT = os.path.join(CERTS_DIR, 'profile_cert.pem')
PROFILE_KEY = os.path.join(CERTS_DIR, 'profile_key.pem')
SETTINGS_PATH = os.path.join(CERTS_DIR, 'server_state.json')

# helper to persist simple server settings (default_signing)
import json

def _load_settings():
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as fh:
                return json.load(fh)
    except Exception:
        pass
    return {"default_signing": False}


def _save_settings(d: dict):
    try:
        with open(SETTINGS_PATH, 'w', encoding='utf-8') as fh:
            json.dump(d, fh)
    except Exception:
        pass


def _get_default_signing():
    return bool(_load_settings().get('default_signing', False))


def _set_default_signing(v: bool):
    s = _load_settings()
    s['default_signing'] = bool(v)
    _save_settings(s)


@app.route('/')
def index():
    return send_from_directory('web', 'captive_portal.html')


@app.route('/profile.mobileconfig')
def profile_mobileconfig():
    ssid = request.args.get('ssid', 'TuRedWiFi')
    dns = request.args.get('dns', '1.1.1.1')
    sign = request.args.get('sign', '0')
    dns_list = [d.strip() for d in dns.split(',') if d.strip()]
    builder = MobileConfigBuilder(display_name=f"Profile for {ssid}", identifier_base='com.jarvis.profile')
    builder.add_wifi_payload(ssid=ssid, password=None, encryption=None, dns_servers=dns_list)
    data = builder.as_bytes()

    # decide if signing is requested explicitly or by server default
    should_sign = str(sign).lower() in ('1', 'true', 'yes') or _get_default_signing()

    # only attempt signing if certs are available
    if should_sign:
        if os.path.exists(PROFILE_CERT) and os.path.exists(PROFILE_KEY):
            try:
                signed = sign_profile_with_openssl(data, PROFILE_CERT, PROFILE_KEY)
                resp = make_response(signed)
                resp.headers['Content-Type'] = 'application/x-apple-aspen-config'
                resp.headers['Content-Disposition'] = f'attachment; filename="{ssid}_profile.signed.mobileconfig"'
                return resp
            except Exception as e:
                return jsonify({'ok': False, 'error': 'signing failed', 'details': str(e)}), 500
        else:
            # requested but not available -> return informative error
            return jsonify({'ok': False, 'error': 'signing-unavailable', 'details': 'profile cert/key not found on server'}), 503

    resp = make_response(data)
    resp.headers['Content-Type'] = 'application/x-apple-aspen-config'
    resp.headers['Content-Disposition'] = f'attachment; filename="{ssid}_profile.mobileconfig"'
    return resp


@app.route('/qr.png')
def qr_png():
    data = request.args.get('data', request.host_url)
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return (buf.getvalue(), 200, {'Content-Type': 'image/png'})


# --- Static serving for logs / uploaded files ---
@app.route('/logs/<path:fname>')
def serve_log_file(fname):
    return send_from_directory(LOG_DIR, fname)


@app.route('/upload-recovery', methods=['POST'])
def upload_recovery():
    """Recibe un archivo recovery (multipart/form-data) y lo guarda en logs/ y devuelve URL pública relativa."""
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'file missing'}), 400
    f = request.files['file']
    filename = f.filename or f'recovery_{int(time.time())}.pdf'
    safe_name = filename.replace('..', '_')
    out_path = os.path.join(LOG_DIR, safe_name)
    f.save(out_path)
    return jsonify({'ok': True, 'url': url_for('serve_log_file', fname=safe_name, _external=True)})


@app.route('/device-status')
def device_status():
    udid = request.args.get('udid')
    if not udid:
        return jsonify({'error': 'udid required'}), 400
    try:
        st = get_activation_status(udid)
        return jsonify({'ok': True, 'status': st})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/generate-ssl', methods=['POST'])
def generate_ssl():
    """Genera un certificado TLS auto‑firmado para el servidor y (opcional) un certificado para firmar perfiles.

    Devuelve los paths (server_cert, server_key, profile_cert, profile_key).
    """
    if not CRYPTO_AVAILABLE:
        return jsonify({'ok': False, 'error': 'cryptography not installed'}), 500
    # generate server cert
    def gen_cert(cert_path, key_path, cn):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
        # Build SANs: include localhost and loopback, plus the primary local IP if available
        import datetime as _dt, socket, ipaddress
        san_entries = [x509.DNSName('localhost')]
        try:
            san_entries.append(x509.IPAddress(ipaddress.IPv4Address('127.0.0.1')))
        except Exception:
            pass
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            san_entries.append(x509.IPAddress(ipaddress.ip_address(local_ip)))
        except Exception:
            # ignore if cannot determine local IP
            pass
        san = x509.SubjectAlternativeName(san_entries)

        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(_dt.datetime.now(_dt.timezone.utc))
            .not_valid_after(_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=365))
            .add_extension(san, critical=False)
            .sign(key, hashes.SHA256())
        )
        with open(key_path, 'wb') as kf:
            kf.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
        with open(cert_path, 'wb') as cf:
            cf.write(cert.public_bytes(serialization.Encoding.PEM))

    try:
        gen_cert(SERVER_CERT, SERVER_KEY, 'Jarvis Portal Local')
        gen_cert(PROFILE_CERT, PROFILE_KEY, 'Jarvis Profile Signer')
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    return jsonify({'ok': True, 'server_cert': SERVER_CERT, 'server_key': SERVER_KEY, 'profile_cert': PROFILE_CERT, 'profile_key': PROFILE_KEY})



@app.route('/activation-log', methods=['POST'])
def activation_log():
    """Endpoint para registrar requests de diagnóstico que puedas redirigir a través del captive portal.

    WARNING: No use para suplantar servicios de terceros. Solo logs para diagnóstico.
    """
    payload = {
        'headers': dict(request.headers),
        'args': request.args.to_dict(),
        'body': request.get_data(as_text=True)
    }
    fname = os.path.join(LOG_DIR, 'activation_requests.log')
    with open(fname, 'a', encoding='utf-8') as fh:
        fh.write(str(payload) + '\n---\n')
    return jsonify({'ok': True})


@app.route('/certs/<path:fname>')
def serve_cert(fname):
    """Servir certificados generados para descarga (server.crt, profile_cert.pem)."""
    safe = fname.replace('..', '_')
    path = os.path.join(CERTS_DIR, safe)
    if not os.path.exists(path):
        return jsonify({'ok': False, 'error': 'not found'}), 404
    return send_from_directory(CERTS_DIR, safe, as_attachment=True)


@app.route('/signing-status')
def signing_status():
    """Devuelve si la firma de perfiles está disponible y si está habilitada por defecto."""
    available = os.path.exists(PROFILE_CERT) and os.path.exists(PROFILE_KEY)
    enabled = _get_default_signing()
    return jsonify({'ok': True, 'available': available, 'enabled': enabled})


@app.route('/set-signing', methods=['POST'])
def set_signing():
    """Activa / desactiva la firma server-side por defecto si la llave/cert están disponibles."""
    data = request.get_json(silent=True) or {}
    want = bool(data.get('enabled'))
    available = os.path.exists(PROFILE_CERT) and os.path.exists(PROFILE_KEY)
    if want and not available:
        return jsonify({'ok': False, 'error': 'signing-unavailable'}), 400
    _set_default_signing(want)
    return jsonify({'ok': True, 'enabled': _get_default_signing(), 'available': available})


@app.route('/reload', methods=['POST'])
def reload_server():
    """Reinicia el proceso del servidor Flask (solo desde localhost).

    Se devuelve respuesta inmediatamente y el servidor se reinicia en segundo plano.
    """
    if request.remote_addr not in ('127.0.0.1', '::1'):
        return jsonify({'ok': False, 'error': 'forbidden'}), 403
    import threading, sys, os, time
    def _reexec():
        time.sleep(0.6)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    threading.Thread(target=_reexec, daemon=True).start()
    return jsonify({'ok': True, 'restarting': True})


@app.route('/recovery-kit', methods=['POST'])
def recovery_kit():
    """Genera y devuelve el Recovery Kit en el formato solicitado (md|txt|pdf).

    Si fmt=pdf el endpoint devuelve el PDF como attachment (requerirá reportlab).
    """
    data = request.get_json(force=True)
    device = data.get('device', {})
    requester = data.get('requester', 'Soporte')
    fmt = (data.get('format', 'md') or 'md').lower()
    out_name = f"recovery_kit_{device.get('serial','unknown')}.{fmt}"
    out_path = os.path.join(LOG_DIR, out_name)
    p = recovery_docs.generate_recovery_kit(device, requester, proof_of_purchase_path=data.get('proof'), out_path=out_path, fmt=fmt)
    # devolver el archivo como attachment
    try:
        return send_from_directory(LOG_DIR, os.path.basename(p), as_attachment=True)
    except Exception:
        return jsonify({'ok': False, 'error': 'no se pudo generar/servir el archivo', 'path': p}), 500


if __name__ == '__main__':
    # If server certs exist, run with HTTPS
    if os.path.exists(SERVER_CERT) and os.path.exists(SERVER_KEY):
        print('Starting portal_server on https://0.0.0.0:5000 (TLS)')
        app.run(host='0.0.0.0', port=5000, ssl_context=(SERVER_CERT, SERVER_KEY), debug=True)
    else:
        print('Starting portal_server on http://0.0.0.0:5000 (no TLS)')
        app.run(host='0.0.0.0', port=5000, debug=True)
