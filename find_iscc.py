import os
candidates=['C:\\Program Files\\Inno Setup 6','C:\\Program Files (x86)\\Inno Setup 6','C:\\Program Files','C:\\Program Files (x86)']
found=[]
for base in candidates:
    for root,dirs,files in os.walk(base):
        if 'ISCC.exe' in files:
            found.append(os.path.join(root,'ISCC.exe'))
print('\n'.join(found) if found else 'NOT_FOUND')
