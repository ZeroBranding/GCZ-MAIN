# --- Configuration ---
$VenvDir = ".venv"
$RequirementsFile = "requirements.txt"
$PythonVersionMin = [version]"3.10"

# --- Helper Functions ---
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

# --- Pre-flight Checks ---
Write-Info "Starting setup..."

# Check if Python is installed
try {
    $python_path = Get-Command python
    Write-Info "Python found at: $($python_path.Source)"
}
catch {
    Write-Error "Python is not installed or not in PATH. Please install it before running this script."
}

# Check Python version
$python_version_output = (python --version)
$python_version_string = ($python_version_output -split ' ')[1]
$python_version_current = [version]$python_version_string

if ($python_version_current -lt $PythonVersionMin) {
    Write-Warn "Current Python version is $python_version_current, but >= $PythonVersionMin is recommended."
}

# --- Virtual Environment Setup ---
if (Test-Path -Path $VenvDir) {
    Write-Info "Virtual environment '$VenvDir' already exists."
}
else {
    Write-Info "Creating Python virtual environment in '$VenvDir'..."
    python -m venv $VenvDir
}

# Activate the virtual environment
. "$($VenvDir)\Scripts\Activate.ps1"
Write-Info "Virtual environment activated."

# --- Dependency Installation ---
if (Test-Path -Path $RequirementsFile) {
    Write-Info "Installing dependencies from '$RequirementsFile'..."
    pip install -r $RequirementsFile
    Write-Info "Dependencies installed successfully."
}
else {
    Write-Error "Could not find '$RequirementsFile'. Please ensure the file exists in the root directory."
}

# --- Hardware Checks (Non-blocking) ---
Write-Info "Performing hardware checks..."

# Check for NVIDIA GPU and CUDA
try {
    $nvidia_smi_output = nvidia-smi.exe --query-gpu=driver_version,cuda_version --format=csv,noheader,nounits
    Write-Info "NVIDIA GPU detected."
    Write-Info "CUDA Version: $nvidia_smi_output"
}
catch {
    Write-Info "No NVIDIA GPU detected with nvidia-smi. Some features may be unavailable or run on CPU."
}

Write-Info "Setup complete. To activate the environment, run: .\\$($VenvDir)\Scripts\Activate.ps1"
