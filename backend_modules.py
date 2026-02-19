# backend_modules.py
import subprocess
import re
import tempfile
import os
import shutil
import time

# ---- Utilidades ----
def _run(cmd, timeout=30):
    """Ejecuta comando y devuelve (stdout, stderr). Lanza FileNotFoundError si no existe.

    En Windows evitamos que los procesos hijos creen consolas visibles usando
    `creationflags=subprocess.CREATE_NO_WINDOW` y `STARTUPINFO` si procede.
    """
    run_kwargs = {"capture_output": True, "text": True, "timeout": timeout}
    if os.name == "nt":
        # Evitar consolas visibles en Windows
        try:
            run_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        except AttributeError:
            pass
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            run_kwargs["startupinfo"] = si
        except Exception:
            pass
    proc = subprocess.run(cmd, **run_kwargs)
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    return stdout, stderr, proc.returncode


def _stream(cmd, timeout=None):
    """Ejecuta comando y recoge stdout combinado (uso simple).

    Aseguramos que en Windows los procesos hijos no muestren una consola.
    """
    popen_kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "text": True, "bufsize": 1}
    if os.name == "nt":
        try:
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        except AttributeError:
            pass
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            popen_kwargs["startupinfo"] = si
        except Exception:
            pass
    p = subprocess.Popen(cmd, **popen_kwargs)
    out = []
    for line in iter(p.stdout.readline, ""):
        out.append(line)
    p.wait()
    return "".join(out), p.returncode


def _run_with_retries(cmd, timeout=30, retries=2, delay=0.6):
    """Ejecuta `_run` con reintentos para errores transitorios relacionados con lockdownd/mux."""
    last_out = last_err = None
    for attempt in range(retries + 1):
        out, err, rc = _run(cmd, timeout=timeout)
        last_out, last_err = out, err
        combined = (out or "") + (err or "")
        if rc == 0:
            return out, err, rc
        if re.search(r'lockdownd|mux error|invalid hostid', combined, re.I) and attempt < retries:
            time.sleep(delay)
            continue
        return out, err, rc
    return last_out, last_err, rc


def _stream_with_retries(cmd, timeout=None, retries=2, delay=0.6):
    """Ejecuta `_stream` con reintentos para errores transitorios relacionados con lockdownd/mux."""
    last_out = None
    for attempt in range(retries + 1):
        out, rc = _stream(cmd, timeout=timeout)
        last_out = out
        if rc == 0:
            return out, rc
        if re.search(r'lockdownd|mux error|invalid hostid', out, re.I) and attempt < retries:
            time.sleep(delay)
            continue
        return out, rc
    return last_out, rc

# ---- Funciones públicas ----
def list_devices():
    try:
        out, err, rc = _run_with_retries(["idevice_id", "-l"], timeout=5, retries=2)
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
        out, err, rc = _run_with_retries(["ideviceinfo", "-u", udid], timeout=8, retries=2)
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
    # Prefer explicit keys that contain 'imei' to avoid false matches inside other words
    imei = None
    # 1) Prefer explicit keys that clearly indicate IMEI (exact or ending with 'imei')
    for k, v in info.items():
        kl = re.sub(r"\W+", "", k or "").lower()
        if kl == "imei" or kl.endswith("imei") or "internationalmobileequipmentidentity" in kl:
            imei = (v or "").strip()
            break
    # 2) If not found, prefer any value that *looks like* an IMEI (15-16 digit number)
    if not imei:
        for v in info.values():
            if isinstance(v, str) and re.fullmatch(r"\d{14,16}", v.strip()):
                imei = v.strip()
                break
    # 3) fallback: search raw output for word-boundary 'IMEI' followed by digits/word
    if not imei:
        imei = find_regex(r"\bIMEI\b[:\s]*([0-9A-Za-z]+)")
    if isinstance(imei, str):
        imei = imei.strip()
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
            out, err, rc = _run_with_retries(cmd, timeout=12, retries=2)
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
        out, rc = _stream_with_retries(["idevicecrashreport", "-u", udid, tmpdir], retries=2)
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
            out, err, rc = _run_with_retries(cmd, timeout=12, retries=2)
            combined += out + err
            if out.strip():
                break
        except FileNotFoundError:
            continue
    if not combined:
        raise RuntimeError("No se pudo obtener ticket; revisa que 'ideviceactivation' esté instalado y el dispositivo esté emparejado.")
    return combined


def get_activation_status(udid: str):
    """Comprueba el estado de activación del dispositivo.

    Devuelve un dict con keys: activation_state (str|None), activation_lock (bool), raw (str).
    Usa `ideviceinfo -k ActivationState` y `ideviceactivation activation-info` cuando estén disponibles.
    """
    status = {"activation_state": None, "activation_lock": False, "raw": ""}
    # 1) intentar ideviceinfo -k ActivationState
    try:
        out, err, rc = _run_with_retries(["ideviceinfo", "-u", udid, "-k", "ActivationState"], timeout=6)
        if rc == 0 and out and out.strip():
            status["activation_state"] = out.strip()
            status["raw"] += out
    except FileNotFoundError:
        pass
    # 2) intentar ideviceactivation activation-info (más detalles)
    try:
        out2, err2, rc2 = _run_with_retries(["ideviceactivation", "-u", udid, "activation-info"], timeout=8)
        if out2:
            status["raw"] += "\n" + out2
            if re.search(r'ActivationLock|activation locked', out2, re.I):
                status["activation_lock"] = True
    except FileNotFoundError:
        pass
    # 3) fallback: parse ideviceinfo completo
    try:
        out3, err3, rc3 = _run_with_retries(["ideviceinfo", "-u", udid], timeout=8)
        if out3:
            status["raw"] += "\n" + out3
            if not status["activation_state"]:
                m = re.search(r'ActivationState\s*:\s*(\w+)', out3, re.I)
                if m:
                    status["activation_state"] = m.group(1)
            if re.search(r'ActivationLock|activation locked', out3, re.I):
                status["activation_lock"] = True
    except FileNotFoundError:
        pass
    return status


def restart_springboard(udid: str):
    """Pide reinicio del SpringBoard vía idevicediagnostics."""
    cmds = [
        ["idevicediagnostics", "restart", "-u", udid],
        ["idevicediagnostics", "restart", udid]
    ]
    for cmd in cmds:
        try:
            out, err, rc = _run_with_retries(cmd, timeout=8, retries=2)
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
