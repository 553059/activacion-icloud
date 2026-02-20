import os, subprocess, sys
candidates=[r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe"]
iss = os.path.join('installer','jarvis_installer.iss')
for c in candidates:
    if os.path.exists(c):
        print('FOUND', c)
        cmd = [c, iss]
        print('RUNNING', ' '.join(cmd))
        r = subprocess.run(cmd, capture_output=True, text=True)
        print('RC', r.returncode)
        print('STDOUT')
        print(r.stdout)
        print('STDERR')
        print(r.stderr)
        sys.exit(r.returncode)
print('ISCC_NOT_FOUND')
sys.exit(2)
