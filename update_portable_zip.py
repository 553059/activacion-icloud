import zipfile, shutil, os, tempfile
src='dist/main.exe'
zip_path='installer/jarvis_portable.zip'
with tempfile.TemporaryDirectory() as td:
    with zipfile.ZipFile(zip_path,'r') as z:
        z.extractall(td)
    shutil.copy(src, os.path.join(td, 'main.exe'))
    with zipfile.ZipFile(zip_path,'w', zipfile.ZIP_DEFLATED) as z2:
        for root,dirs,files in os.walk(td):
            for f in files:
                full=os.path.join(root,f)
                arc=os.path.relpath(full, td)
                z2.write(full, arc)
print('UPDATED_ZIP')
