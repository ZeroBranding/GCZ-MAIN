<#
.SYNOPSIS
    Processes voice training jobs from the queue directory.
    This script looks for 'train_voice' job files, unzips the audio data,
    and generates an OpenVoice speaker embedding.

.DESCRIPTION
    The script performs the following steps:
    1. Sets the base path relative to the script's location.
    2. Defines paths for the queue, voice data, and voice models directories.
    3. Searches for pending 'train_voice_*.json' job files in the queue.
    4. For each job file:
        a. Marks the job as 'processing'.
        b. Reads job details (voice name, zip path).
        c. Extracts the ZIP file into a temporary 'unpacked' directory.
        d. Finds the first .wav or .mp3 file in the unpacked directory to use as a reference.
        e. Creates the target directory for the voice model.
        f. Defines the output path for the speaker embedding (.pth file).
        g. Executes the 'openvoice' command-line tool to generate the embedding.
        h. If successful, updates the job file status to 'completed' and cleans up the unpacked data.
        i. If it fails, marks the job as 'failed' and logs the error.
#>

# --- Configuration ---
$ScriptPath = $MyInvocation.MyCommand.Path
$BaseDir = Resolve-Path (Join-Path $ScriptPath "..\..\..") # Assumes script is in scripts/win/
$QueueDir = Join-Path $BaseDir "data\queue"
$VoiceDataDir = Join-Path $BaseDir "data\voice"
$VoiceModelDir = Join-Path $BaseDir "models\voice"

# --- Main Logic ---
Write-Host "Starting OpenVoice Training Job Processor..."

$jobFiles = Get-ChildItem -Path $QueueDir -Filter "train_voice_*.json"

if ($jobFiles.Count -eq 0) {
    Write-Host "No pending voice training jobs found."
    exit 0
}

foreach ($jobFile in $jobFiles) {
    $jobFilePath = $jobFile.FullName
    $job = Get-Content -Path $jobFilePath | ConvertFrom-Json

    # Check if job is pending
    if ($job.status -ne "pending") {
        Write-Host "Skipping job $($jobFile.Name) with status $($job.status)."
        continue
    }

    Write-Host "Processing job: $($jobFile.Name) for voice '$($job.voice_name)'"

    try {
        # Mark job as processing
        $job.status = "processing"
        $job | ConvertTo-Json | Set-Content -Path $jobFilePath

        # Paths
        $zipPath = $job.zip_path
        $voiceName = $job.voice_name
        $unpackedDir = Join-Path $VoiceDataDir $voiceName "unpacked"
        $targetModelDir = Join-Path $VoiceModelDir $voiceName
        $embeddingPath = Join-Path $targetModelDir "openvoice_embedding.pth"
        
        # Ensure directories exist
        New-Item -ItemType Directory -Path $unpackedDir -Force | Out-Null
        New-Item -ItemType Directory -Path $targetModelDir -Force | Out-Null
        
        # Unzip the audio files
        Write-Host "Unpacking '$zipPath' to '$unpackedDir'..."
        Expand-Archive -Path $zipPath -DestinationPath $unpackedDir -Force
        
        # Find a reference audio file (first wav or mp3)
        $referenceAudio = Get-ChildItem -Path $unpackedDir -Recurse -Include *.wav, *.mp3 | Select-Object -First 1
        
        if (-not $referenceAudio) {
            throw "No .wav or .mp3 files found in the provided ZIP archive."
        }
        
        $referenceAudioPath = $referenceAudio.FullName
        Write-Host "Found reference audio: $referenceAudioPath"
        
        # Run OpenVoice embedding extraction
        # Assumes 'openvoice' is in the system's PATH (installed via pip)
        Write-Host "Generating speaker embedding using OpenVoice..."
        & openvoice --extract-se --audio-path-in "$referenceAudioPath" --path-se-out "$embeddingPath"
        
        if (Test-Path $embeddingPath) {
            Write-Host "Successfully created speaker embedding at '$embeddingPath'"
            
            # Update job status to completed
            $job.status = "completed"
            $job.embedding_path = $embeddingPath
            $job | ConvertTo-Json | Set-Content -Path $jobFilePath
            
            # Clean up unpacked files
            Write-Host "Cleaning up temporary unpacked files..."
            Remove-Item -Path $unpackedDir -Recurse -Force
        } else {
            throw "OpenVoice embedding generation failed. Output file not found."
        }

        Write-Host "Successfully processed job for voice '$voiceName'."

    } catch {
        Write-Error "Failed to process job $($jobFile.Name). Reason: $_"
        $job.status = "failed"
        $job.error = $_.ToString()
        $job | ConvertTo-Json | Set-Content -Path $jobFilePath
    }
}

Write-Host "OpenVoice Training Job Processor finished."
