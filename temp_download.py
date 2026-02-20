import json, subprocess, os, shutil
p='artifacts_list.json'
encodings_to_try = ['utf-8', 'utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'latin-1']
j = None
last_exc = None
for enc in encodings_to_try:
    try:
        with open(p, 'r', encoding=enc) as f:
            j = json.load(f)
        break
    except Exception as e:
        last_exc = e
if j is None:
    raise last_exc
arts=j.get('artifacts',[])
if arts:
    a=arts[0]
    aid=a['id']; name=a['name']
    os.makedirs('artifacts',exist_ok=True)
    print('FOUND', aid, name)
    cmd = f'& "C:\\Program Files\\GitHub CLI\\gh.exe" api repos/553059/activacion-icloud/actions/artifacts/{aid}/zip --method GET --header "Accept: application/zip" --raw > "artifacts/{name}.zip"'
    print('RUN:', cmd)
    subprocess.run(cmd, shell=True)
    print('DOWNLOADED:', os.path.join('artifacts', name + '.zip'))
else:
    print('NO_ARTIFACTS')
    os.makedirs('artifacts',exist_ok=True)
    if os.path.exists('ci_run_22149764559.log'):
        shutil.copy('ci_run_22149764559.log','artifacts\\ci_run_22149764559.log')
        print('COPIED_LOG to artifacts\\ci_run_22149764559.log')
    else:
        print('LOG_NOT_FOUND')
