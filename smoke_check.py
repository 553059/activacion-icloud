import os, subprocess, time, json
from pathlib import Path
import backend_modules as backend

print('Starting smoke checks')
# Ensure app is running (start if not)
exe = r'C:\Users\emili\AppData\Local\Programs\Jarvis\main.exe'
started = False
for p in subprocess.run(['tasklist'], capture_output=True, text=True).stdout.splitlines():
    if 'main.exe' in p.lower():
        started = True
        break
if not started:
    try:
        os.startfile(exe)
        print('Launched app executable')
    except Exception as e:
        print('Failed to launch app:', e)

# Helper to print result
def run_and_print(fn, *args, **kwargs):
    name = fn.__name__
    print(f"\n--- {name} ---")
    try:
        r = fn(*args, **kwargs)
        print('OK ->', type(r), r if isinstance(r, (str, int, list, dict)) else 'result (hidden)')
    except Exception as e:
        print('EXCEPTION ->', repr(e))

# 1) list_devices
run_and_print(backend.list_devices)

devices = backend.list_devices()
if devices:
    udid = devices[0]
    # 2) get_device_info
    run_and_print(backend.get_device_info, udid)
    # 3) extract_owner_info
    run_and_print(backend.extract_owner_info, udid)
    # 4) analyze_panics (may require idevicecrashreport)
    run_and_print(backend.analyze_panics, udid)
    # 5) request_activation_ticket
    run_and_print(backend.request_activation_ticket, udid)
    # 6) restart_springboard
    run_and_print(backend.restart_springboard, udid)
else:
    print('\nNo devices found; skipping device-level smoke tests')

# Tail latest log file for 8 seconds
logs = list(Path('logs').glob('jarvis_logs_*.txt'))
if logs:
    latest = max(logs, key=lambda p: p.stat().st_mtime)
    print(f"\nTailing log {latest} for 8s...\n")
    with open(latest, 'r', encoding='utf-8', errors='ignore') as fh:
        fh.seek(0, 2)
        end = time.time() + 8
        while time.time() < end:
            line = fh.readline()
            if line:
                print(line.rstrip())
            else:
                time.sleep(0.2)
else:
    print('\nNo log files found to tail')

print('\nSmoke checks completed')
