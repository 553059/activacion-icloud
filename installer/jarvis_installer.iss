; JARVIS ULTIMATE TOOL — Inno Setup script
[Setup]
AppName=JARVIS ULTIMATE TOOL
AppVersion=1.0.0
AppPublisher=JARVIS ING
DefaultDirName={pf}\JARVIS ULTIMATE TOOL v1.0
DefaultGroupName=JARVIS ULTIMATE TOOL
OutputBaseFilename=JARVIS_Ultimate_Tool_v1.0_Setup
Compression=lzma2/ultra
SolidCompression=yes
SetupIconFile=assets\jarvis_icon.ico

[Files]
Source: "dist\main.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "assets\*"; DestDir: "{app}\assets"; Flags: recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\JARVIS ULTIMATE TOOL"; Filename: "{app}\main.exe"; IconFilename: "{app}\assets\jarvis_icon.ico"
Name: "{userdesktop}\JARVIS ULTIMATE TOOL"; Filename: "{app}\main.exe"; Tasks: desktopicon; IconFilename: "{app}\assets\jarvis_icon.ico"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Run]
Filename: "{app}\main.exe"; Description: "Iniciar JARVIS ULTIMATE TOOL"; Flags: nowait postinstall skipifsilent
