# PowerShell script to download Real-ESRGAN models

# Destination directory for the models
$destination = "external/Real-ESRGAN/weights"

# Ensure the destination directory exists
if (-Not (Test-Path -Path $destination)) {
    New-Item -ItemType Directory -Path $destination -Force
}

# Model URLs
$models = @{
    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth" = "RealESRGAN_x4plus.pth";
    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth" = "RealESRGAN_x4plus_anime_6B.pth";
    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth" = "realesr-animevideov3.pth";
}


# Download models
$models.GetEnumerator() | ForEach-Object {
    $url = $_.Name
    $fileName = $_.Value
    $output = Join-Path -Path $destination -ChildPath $fileName
    if (-Not (Test-Path $output)) {
        Write-Output "Downloading: $fileName"
        Invoke-WebRequest -Uri $url -OutFile $output
        Write-Output "Downloaded: $fileName"
    } else {
        Write-Output "Already exists: $fileName"
    }
}
