import subprocess
out = subprocess.run(['tasklist'], capture_output=True, text=True)
for line in out.stdout.splitlines():
    if 'main.exe' in line.lower():
        print('FOUND_PROCESS:', line)
        break
else:
    print('main.exe not found')
