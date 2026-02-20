# JARVIS ULTIMATE TOOL v1.0

Herramienta de escritorio (Python) para diagnóstico y utilidades iOS — UI moderna con `customtkinter`.

## Requisitos
- Python 3.10+
- libimobiledevice (idevice_id, ideviceinfo, idevicecrashreport, ideviceactivation, idevicediagnostics) en PATH
- OpenSSL CLI (recomendado) — necesaria para firmar `mobileconfig` con la utilidad `openssl`. El proyecto tiene un *fallback* que usa `cryptography` cuando `openssl` no está disponible, pero para interoperabilidad y verificación en dispositivos reales se recomienda instalar el binario.
- Windows: ejecuta la app con permisos de administrador si el dispositivo no aparece

### Generar / instalar `server.crt` y uso para MITM local
- El servidor puede generar automáticamente un certificado TLS con `/generate-ssl` (portal local).
- Para que iOS confíe en el MITM local y permita la descarga/instalación de perfiles firmados, instala `server.crt` y `profile_cert.pem` en el iPhone y marca la confianza en *Ajustes → General → Acerca de → Ajustes de confianza de certificados*.
- Comandos OpenSSL (si prefieres generar manualmente):

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout server.key -out server.crt -subj "/CN=Jarvis Portal Local"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout profile_key.pem -out profile_cert.pem -subj "/CN=Jarvis Profile Signer"
```

- Nota: el DNS interception necesita que el iPhone resuelva `albert.apple.com`, `gs.apple.com`, `captive.apple.com` hacia tu máquina. Puedes usar `scripts/dns_server.py` (dnslib) o configurar manualmente el DNS del iPhone para apuntar al servidor local.


## Instalación rápida
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecutar
```bash
python main.py
```

## Empaquetar a .exe (Windows)
1. pip install pyinstaller
2. pyinstaller --noconfirm --onefile --windowed --add-data "assets;assets" --icon=assets/jarvis_icon.ico main.py
3. Ejecutable en `dist\main.exe`

## Instalador Windows (Inno Setup)
Generamos un instalador .exe (setup) usando Inno Setup. Hay dos opciones:

- Local (tu máquina Windows): instala Inno Setup, ejecuta PyInstaller y compila el .iss.
- En CI: hay un job que genera el instalador y lo deja como artifact.

Instrucciones (local):

1. Asegúrate de tener Inno Setup (`ISCC.exe`) instalado o Chocolatey (para instalarlo).
2. Ejecuta el script helper:

```powershell
# desde la raíz del repo
.\scripts\build_installer.ps1
```

3. Resultado: `installer\JARVIS_Ultimate_Tool_v1.0_Setup.exe` (si Inno Setup estuvo disponible).

Instrucciones (CI):
- El workflow de GitHub Actions `CI` incluye el job `build_installer` (Windows) que crea y sube el instalador como artifact.


## Módulos principales
- `main.py` — Interfaz (GUI)
- `backend_modules.py` — Wrappers a `libimobiledevice` + parsers

## Notas
- Algunas funciones dependen de las utilidades nativas y del dispositivo emparejado.
- Sustituye `assets/jarvis_icon.ico` por tu icono real antes de generar el .exe.

---

## Pruebas con dispositivo iOS (manual)
Para validar detección y comandos en un dispositivo físico conectado por USB:

1. Conecta el iPhone/iPad por USB y asegúrate de que esté emparejado en tu sistema.
2. Ejecuta el script de prueba rápido:

```bash
python scripts/device_smoke.py --list
python scripts/device_smoke.py --info <UDID>
python scripts/device_smoke.py --activation <UDID>
```

3. Ejecuta la aplicación GUI y usa los botones (Dashboard / Pánicos / Servidor) para pruebas interactivas.

Consejos:
- En Windows ejecuta la app como Administrador si no detecta el dispositivo.
- Asegúrate de tener instalados los drivers y `libimobiledevice` en `PATH`.

## Tests y CI
- Ejecutar tests localmente: `python -m pytest -q`.
- La suite incluye parsers, mocks y un test de humo de GUI. El test de GUI se omite automáticamente en CI headless.
- CI: hay un workflow de GitHub Actions en `.github/workflows/ci.yml` que ejecuta los tests en cada push/PR (Windows + Ubuntu, Python 3.10/3.11).

### OpenSSL & profile signing
- Recomendado: instala el binario `openssl` en tu sistema para poder generar y verificar perfiles `.mobileconfig` firmados con la utilidad `openssl`.
  - Windows: instala el instalador **Win64 OpenSSL** o usa Chocolatey: `choco install openssl.light`
  - macOS / Linux: `brew install openssl` / `sudo apt install openssl`
- El servidor local (`portal_server.py`) intentará usar `openssl` cuando `sign=1` en `/profile.mobileconfig`. Si no detecta `openssl`, el proyecto ofrece un **fallback** que usa `cryptography` para firmar archivos (no requiere el CLI), de forma que la funcionalidad de firma sigue disponible en entornos sin `openssl`.

### Verificación automática (`scripts/verify_setup.py`)
- Hay un script de comprobación automática: `scripts/verify_setup.py` — valida imports, arranca el portal, prueba endpoints (profile/mobileconfig, qr, recovery-kit) y ejecuta un headless smoke.
- Úsalo localmente: `python scripts/verify_setup.py --run-tests`.
- El script también comprueba si `openssl` está disponible y reporta warnings si no lo está.

### CI: verificación en PRs
- He añadido un job (GitHub Actions) que ejecuta `scripts/verify_setup.py` en cada PR para garantizar que el servidor y endpoints principales funcionan en Ubuntu/Windows. Ver `.github/workflows/verify-setup.yml`.


