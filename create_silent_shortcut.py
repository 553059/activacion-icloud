import os
import winshell

desktop = winshell.desktop()
shortcut_path = os.path.join(desktop, 'Jarvis - Silent.lnk')

target = r'C:\\Users\\emili\\AppData\\Local\\Programs\\Jarvis\\main.exe'

with winshell.shortcut(shortcut_path) as shortcut:
    shortcut.path = target
    shortcut.window_style = 7  # Minimized

print(f"SHORTCUT_CREATED {shortcut_path}")