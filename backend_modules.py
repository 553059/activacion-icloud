# backend_modules.py
import subprocess
import re
import tempfile
import os
import shutil

# ---- Utilidades ----
def _run(cmd, timeout=30):
    """Ejecuta comando y devuelve (stdout, stderr). Lanza FileNotFoundError si no existe."""
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    return stdout, stderr, proc.returncode

def _stream(cmd, timeout=None):
    """Ejecuta comando y recoge stdout combinado (uso simple)."""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    out = []
    for line in iter(p.stdout.readline, ""):
        out.append(line)
    p.wait()
    return "".join(out), p.returncode

# ---- Funciones públicas ----
def list_devices():
    try:
        out, err, rc = _run(["idevice_id", "-l"], timeout=5)
    except FileNotFoundError:
        # libimobiledevice no instalado / no en PATH
        return []
    except subprocess.TimeoutExpired:
        return []
    if rc != 0:
        return []
    return [l.strip() for l in out.splitlines() if l.strip()]

def get_device_info(udid: str):
    try:
        out, err, rc = _run(["ideviceinfo", "-u", udid], timeout=8)
    except FileNotFoundError:
        raise RuntimeError("ideviceinfo no disponible en PATH")
    except subprocess.TimeoutExpired:
        raise RuntimeError("ideviceinfo: timed out")
    if rc != 0:
        raise RuntimeError("ideviceinfo falló: " + (err or out))
    info = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            info[k.strip()] = v.strip()
    # Extraer campos clave
    def find_regex(pattern):
        m = re.search(pattern, out, re.IGNORECASE)
        return m.group(1) if m else None
    imei = info.get("IMEI") or find_regex(r"IMEI[:\s]*([0-9A-Za-z]+)")
    return {
        "udid": udid,
        "model": info.get("ProductType") or info.get("DeviceClass") or info.get("DeviceName"),
        "serial": info.get("SerialNumber"),
        "imei": imei,
        "battery_percent": info.get("BatteryCurrentCapacity") or info.get("BatteryPercent"),
        "battery_cycles": info.get("BatteryCycleCount"),
        "ios_version": info.get("ProductVersion"),
        "raw": out
    }

def extract_owner_info(udid: str):
    """Intenta obtener información de activación / propietario y devuelve enmascarada + raw."""
    tries = [
        ["ideviceactivation", "-u", udid, "activation-info"],
        ["ideviceactivation", "-u", udid, "activationrecord"],
        ["ideviceinfo", "-u", udid]
    ]
    combined = ""
    for cmd in tries:
        try:
            out, err, rc = _run(cmd, timeout=12)
            combined += out + err
            if out.strip():
                break
        except FileNotFoundError:
            continue
    # Buscar email / phone en raw
    email = None
    phone = None
    em = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", combined)
    if em:
        email = em.group(0)
    ph = re.search(r"(?:\+?\d[\d\-\s]{6,}\d)", combined)
    if ph:
        phone = ph.group(0)
    return {
        "email": email,
        "email_masked": _mask_email(email) if email else None,
        "phone": phone,
        "phone_masked": _mask_phone(phone) if phone else None,
        "raw": combined
    }

def analyze_panics(udid: str):
    """Descarga crashreports (.ips) y busca palabras clave; devuelve diagnóstico sugerido."""
    tmpdir = tempfile.mkdtemp(prefix="jarvis_ips_")
    try:
        # intentar descargar a tmpdir (idevicecrashreport suele aceptar carpeta destino)
        out, rc = _stream(["idevicecrashreport", "-u", udid, tmpdir])
    except FileNotFoundError:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise RuntimeError("idevicecrashreport no disponible en PATH")
    # buscar archivos
    ips_files = []
    for root, _, files in os.walk(tmpdir):
        for fn in files:
            if fn.lower().endswith((".ips", ".crash", ".panic")):
                ips_files.append(os.path.join(root, fn))
    matches = []
    snippets = ""
    KEYWORDS = ["SMC Panic", "WDT Timeout", r"0x800", "panic", "kernel panic"]
    for path in ips_files:
        try:
            with open(path, "r", errors="ignore") as fh:
                data = fh.read()
                for kw in KEYWORDS:
                    if re.search(kw, data, re.IGNORECASE):
                        matches.append(kw)
                        # extraer snippet
                        m = re.search(r".{0,120}" + re.escape(kw) + r".{0,120}", data, re.IGNORECASE)
                        if m:
                            snippets += f"\n--- {os.path.basename(path)} ---\n" + m.group(0) + "\n"
        except Exception:
            continue
    diagnosis = _diagnose_from_matches(matches)
    return {"files": ips_files, "matches": list(set(matches)), "diagnosis": diagnosis, "snippets": snippets, "raw_cmd_output": out}

def request_activation_ticket(udid: str):
    """Pide ticket/registro de activación y devuelve RAW (XML/JSON) si existe."""
    tries = [
        ["ideviceactivation", "-u", udid, "activation-info"],
        ["ideviceactivation", "-u", udid, "activation-record"],
        ["ideviceinfo", "-u", udid, "-k", "ActivationState"]
    ]
    combined = ""
    for cmd in tries:
        try:
            out, err, rc = _run(cmd, timeout=12)
            combined += out + err
            if out.strip():
                break
        except FileNotFoundError:
            continue
    if not combined:
        raise RuntimeError("No se pudo obtener ticket; revisa que 'ideviceactivation' esté instalado y el dispositivo esté emparejado.")
    return combined

def restart_springboard(udid: str):
    """Pide reinicio del SpringBoard vía idevicediagnostics."""
    cmds = [
        ["idevicediagnostics", "restart", "-u", udid],
        ["idevicediagnostics", "restart", udid]
    ]
    for cmd in cmds:
        try:
            out, err, rc = _run(cmd, timeout=8)
            if rc == 0:
                return out + err
        except FileNotFoundError:
            continue
    raise RuntimeError("idevicediagnostics no disponible o fallo al reiniciar SpringBoard.")

# ---- Helpers internos ----
def _mask_email(email: str):
    if not email or "@" not in email:
        return None
    local, domain = email.split("@", 1)
    return (local[0] + "....." if local else ".....") + "@" + domain

def _mask_phone(phone: str):
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    return ("..." + digits[-4:]) if len(digits) >= 4 else ("..." + digits)

def _diagnose_from_matches(matches):
    if not matches:
        return "No se encontraron patrones críticos en pánicos."
    if any("SMC" in m.upper() for m in matches):
        return "Posible falla de Interposer / SMC (revisar conexiones y SMC)."
    if any("WDT" in m.upper() for m in matches):
        return "Watchdog Timeout detectado — posible problema de power management o firmware."
    if any("0X800" in m.upper() for m in matches):
        return "Código 0x800 detectado — investigar baseband / low-level hardware."
    return "Hallazgos detectados — requiere inspección técnica."
