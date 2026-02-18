# JARVIS ULTIMATE TOOL v1.0

Herramienta de escritorio (Python) para diagnóstico y utilidades iOS — UI moderna con `customtkinter`.

## Requisitos
- Python 3.10+
- libimobiledevice (idevice_id, ideviceinfo, idevicecrashreport, ideviceactivation, idevicediagnostics) en PATH
- Windows: ejecuta la app con permisos de administrador si el dispositivo no aparece

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

