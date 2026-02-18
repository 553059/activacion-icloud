<#
PowerShell helper: construye el .exe (PyInstaller) y empaqueta un instalador (Inno Setup).
Uso: .\scripts\build_installer.ps1  (ejecutar desde la raíz del repo)
Opciones:
  -NoInstallInno  -> no intenta instalar Inno Setup si no está disponible
#>
param(
    [switch]$NoInstallInno
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $root\..   # sitúa en la raíz del repo

Write-Host "Building virtualenv + dependencies..."
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

Write-Host "Running PyInstaller..."
pyinstaller --noconfirm --onefile --windowed --add-data "assets;assets" --icon=assets/jarvis_icon.ico main.py

$exePath = Join-Path -Path (Get-Location) -ChildPath "dist\main.exe"
if (-not (Test-Path $exePath)) {
    Write-Error "PyInstaller no generó dist\\main.exe. Revisa la salida de PyInstaller."
    Pop-Location
    exit 1
}

# Buscar ISCC
$iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    if ($NoInstallInno) {
        Write-Warning "ISCC no disponible y -NoInstallInno fue especificado. Instalador no generado."
        Write-Output "EXE construido en: $exePath"
        Pop-Location
        exit 0
    }
    Write-Host "ISCC no encontrado — instalando Inno Setup vía Chocolatey... (puede requerir permisos)"
    choco install innosetup -y
    $iscc = Get-Command "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" -ErrorAction SilentlyContinue
}

if ($iscc) {
    Write-Host "Compilando instalador (.iss)..."
    & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "installer\jarvis_installer.iss"
    $installer = Get-ChildItem -Path "installer\*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($installer) {
        Write-Host "Instalador generado: $($installer.FullName)"
    } else {
        Write-Warning "No se encontró instalador después de compilar .iss"
    }
} else {
    Write-Warning "ISCC aún no disponible — solo se construyó el EXE: $exePath"
}

Pop-Location
