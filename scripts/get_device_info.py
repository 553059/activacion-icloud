import json
import sys
import backend_modules as bm

if len(sys.argv) < 2:
    print('usage: get_device_info.py <udid>')
    sys.exit(2)
udid = sys.argv[1]
try:
    info = bm.get_device_info(udid)
    print(json.dumps(info, ensure_ascii=False, indent=2))
except Exception as e:
    print('ERROR:', e)
    sys.exit(1)
