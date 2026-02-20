import shutil, os
src=os.path.abspath('installer/Output/JARVIS_Ultimate_Tool_v1.0_Setup.exe')
art=os.path.abspath('artifacts/JARVIS_Ultimate_Tool_v1.0_Setup.exe')
desktop=os.path.join(os.path.expanduser('~'),'Desktop','JARVIS_Ultimate_Tool_v1.0_Setup.exe')
shutil.copy2(src, art)
shutil.copy2(src, desktop)
print('COPIED', art, desktop)
