"""
Script de humo para pruebas manuales con un dispositivo iOS conectado.
Uso:
  python scripts/device_smoke.py --list
  python scripts/device_smoke.py --info <UDID>
  python scripts/device_smoke.py --activation <UDID>
  python scripts/device_smoke.py --panics <UDID>
  python scripts/device_smoke.py --restart <UDID>

Este script usa las funciones de `backend_modules` y está pensado para pruebas manuales.
"""
import argparse
import json
import sys
import backend_modules as backend


def main():
    p = argparse.ArgumentParser(description="Device smoke test for JARVIS ULTIMATE TOOL")
    p.add_argument("--list", action="store_true", help="List connected devices (UDIDs)")
    p.add_argument("--info", metavar="UDID", help="Show device info for UDID")
    p.add_argument("--activation", metavar="UDID", help="Request activation ticket (raw)")
    p.add_argument("--panics", metavar="UDID", help="Download & analyze panic logs")
    p.add_argument("--restart", metavar="UDID", help="Restart SpringBoard on device")
    args = p.parse_args()

    try:
        if args.list:
            devs = backend.list_devices()
            print("Connected UDIDs:")
            if not devs:
                print("  (no devices detected)")
            for d in devs:
                print("  ", d)
            return 0

        if args.info:
            info = backend.get_device_info(args.info)
            print(json.dumps(info, indent=2, ensure_ascii=False))
            return 0

        if args.activation:
            raw = backend.request_activation_ticket(args.activation)
            print(raw)
            return 0

        if args.panics:
            res = backend.analyze_panics(args.panics)
            print("Diagnosis:", res.get("diagnosis"))
            print(res.get("snippets") or "No snippets")
            return 0

        if args.restart:
            out = backend.restart_springboard(args.restart)
            print(out)
            return 0

        p.print_help()
        return 0

    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())