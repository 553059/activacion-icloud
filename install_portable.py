import zipfile, os, shutil, sys
zip_path = os.path.join('installer','jarvis_portable.zip')
if not os.path.exists(zip_path):
    print('ZIP_MISSING')
    sys.exit(2)
fallback = os.path.join(os.environ.get('LOCALAPPDATA',''), 'Programs', 'Jarvis')
os.makedirs(fallback, exist_ok=True)
try:
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(fallback)
except Exception as e:
    print('EXTRACT_FAILED', e)
    sys.exit(1)
# find exe
exe_path = None
for root,dirs,files in os.walk(fallback):
    for f in files:
        if f.lower().endswith('.exe'):
            exe_path = os.path.join(root,f)
            break
    if exe_path:
        break
if not exe_path:
    print('NO_EXE_FOUND')
    sys.exit(3)
# create desktop runner (cmd file)
desktop = os.path.join(os.path.expanduser('~'),'Desktop')
runner = os.path.join(desktop, 'Jarvis - Run.cmd')
with open(runner,'w',encoding='utf-8') as f:
    f.write(f'@echo off\nstart "" "{exe_path}"\n')
print('INSTALLED_TO', fallback)
print('RUNNER', runner)
print('EXECUTABLE', exe_path)
