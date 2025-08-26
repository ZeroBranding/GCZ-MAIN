# --- Configuration ---
$VenvDir = ".venv"
$EnvFile = ".env"
$BotScript = "telegram_bot.py"

# --- Helper Functions ---
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

# --- Pre-flight Checks ---
Write-Info "Starting bot..."

# Check if .env file exists
if (-not (Test-Path -Path $EnvFile)) {
    Write-Error "'.env' file not found. Please copy '.env.template' to '.env' and fill in your configuration."
}

# Check for virtual environment
if (-not (Test-Path -Path $VenvDir)) {
    Write-Error "Virtual environment '$VenvDir' not found. Please run setup.ps1 first."
}

# --- Activate Environment & Run ---
. "$($VenvDir)\Scripts\Activate.ps1"
Write-Info "Virtual environment activated."

Write-Info "Starting the Telegram bot from '$BotScript'..."
Write-Info "Press Ctrl+C to stop the bot."

# The python-dotenv library handles loading the .env file,
# so we just need to run the script.
python $BotScript
