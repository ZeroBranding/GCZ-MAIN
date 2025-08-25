# PowerShell script to download SadTalker models

# Destination directory for the models
$destination = "external/SadTalker/checkpoints"

# Ensure the destination directory exists
if (-Not (Test-Path -Path $destination)) {
    New-Item -ItemType Directory -Path $destination -Force
}

# Model URLs
$models = @{
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/SadTalker_V0.0.2_256.safetensors" = "SadTalker_V0.0.2_256.safetensors";
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/SadTalker_V0.0.2_512.safetensors" = "SadTalker_V0.0.2_512.safetensors";
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/mapping_00229-model.pth.tar" = "mapping_00229-model.pth.tar";
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/mapping_00109-model.pth.tar" = "mapping_00109-model.pth.tar";
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/facevid2vid_00189-model.pth.tar" = "facevid2vid_00189-model.pth.tar";
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/Wav2Lip_original.pth" = "Wav2Lip_original.pth";
}

# BFace models
$bface_models = @{
    "https://github.com/ShowTalker/BFACE_checkpoint/releases/download/v1.0/BFACE_1.0_256.safetensors" = "BFACE_1.0_256.safetensors";
    "https://github.com/ShowTalker/BFACE_checkpoint/releases/download/v1.0/BFACE_1.0_512.safetensors" = "BFACE_1.0_512.safetensors";
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

$bface_models.GetEnumerator() | ForEach-Object {
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


# Dlib models from SadTalker repo
$dlib_models_destination = "external/SadTalker/gfpgan/weights"
if (-Not (Test-Path -Path $dlib_models_destination)) {
    New-Item -ItemType Directory -Path $dlib_models_destination -Force
}

$dlib_models = @{
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/shape_predictor_68_face_landmarks.dat" = "shape_predictor_68_face_landmarks.dat";
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/GFPGANv1.4.pth" = "GFPGANv1.4.pth";
    "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/ParseNet-latest.pth" = "ParseNet-latest.pth";
}

$dlib_models.GetEnumerator() | ForEach-Object {
    $url = $_.Name
    $fileName = $_.Value
    $output = Join-Path -Path $dlib_models_destination -ChildPath $fileName
    if (-Not (Test-Path $output)) {
        Write-Output "Downloading: $fileName to $dlib_models_destination"
        Invoke-WebRequest -Uri $url -OutFile $output
        Write-Output "Downloaded: $fileName"
    } else {
        Write-Output "Already exists: $fileName in $dlib_models_destination"
    }
}
