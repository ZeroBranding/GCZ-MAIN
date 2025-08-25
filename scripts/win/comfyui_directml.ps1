# Mit diesem Skript wird ComfyUI mit DirectML-Unterstützung installiert und eingerichtet.

# Definiert die wichtigsten Verzeichnisse
$basedir = (Get-Item -Path ".." -Verbose).FullName
$externalDir = "$basedir\external"
$comfyUIDir = "$externalDir\ComfyUI"
$comfyUIManagerDir = "$externalDir\ComfyUI-Manager"

# Stellt sicher, dass das externe Verzeichnis existiert
if (-not (Test-Path -Path $externalDir -PathType Container)) {
    New-Item -Path $externalDir -ItemType Directory | Out-Null
}

# Python-Abhängigkeiten installieren
pip install torch-directml
pip install torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu121
pip install comfyui

# Klont oder aktualisiert das ComfyUI-Repository
if (-not (Test-Path -Path $comfyUIDir -PathType Container)) {
    git clone https://github.com/comfyanonymous/ComfyUI.git $comfyUIDir
} else {
    (cd $comfyUIDir; git pull)
}

# Klont oder aktualisiert das ComfyUI-Manager-Repository
if (-not (Test-Path -Path $comfyUIManagerDir -PathType Container)) {
    git clone https://github.com/ltdrdata/ComfyUI-Manager.git $comfyUIManagerDir
} else {
    (cd $comfyUIManagerDir; git pull)
}

# Installiert die AnimateDiff-Nodes über den ComfyUI-Manager
cd $comfyUIManagerDir
python.exe a1111_startup.py --install-glob ComfyUI-AnimateDiff-Evolved

# Erstellt Start- und Stoppskripte
$startScriptContent = @"
cd $comfyUIDir
python main.py
"@
$startScriptContent | Out-File -FilePath "$basedir\scripts\win\start_comfyui.ps1" -Encoding utf8

$stopScriptContent = @"
# Findet und beendet den ComfyUI-Prozess
Get-Process | Where-Object { $_.ProcessName -eq 'python' -and $_.Path -like "*$comfyUIDir*" } | Stop-Process -Force
"@
$stopScriptContent | Out-File -FilePath "$basedir\scripts\win\stop_comfyui.ps1" -Encoding utf8

# Gibt Anweisungen für den manuellen Start aus
Write-Host "ComfyUI (DirectML) und AnimateDiff wurden erfolgreich eingerichtet."
Write-Host "Für den ersten Start führen Sie bitte das folgende Skript manuell aus, um die AnimateDiff-Modelle herunterzuladen:"
Write-Host "$basedir\scripts\win\start_comfyui.ps1"
