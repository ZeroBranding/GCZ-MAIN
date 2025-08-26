#!/bin/bash
set -e

# --- Configuration ---
VENV_DIR=".venv"
ENV_FILE=".env"
BOT_SCRIPT="telegram_bot.py"

# --- Helper Functions ---
info() {
    echo "[INFO] $1"
}

error() {
    echo "[ERROR] $1" >&2
    exit 1
}

# --- Pre-flight Checks ---
info "Starting bot..."

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    error "'.env' file not found. Please copy '.env.template' to '.env' and fill in your configuration."
fi

# Check for virtual environment
if [ ! -d "$VENV_DIR" ]; then
    error "Virtual environment '$VENV_DIR' not found. Please run setup.sh first."
fi

# --- Activate Environment & Run ---
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
info "Virtual environment activated."

info "Starting the Telegram bot from '$BOT_SCRIPT'..."
info "Press Ctrl+C to stop the bot."

# The python-dotenv library handles loading the .env file,
# so we just need to run the script.
python3 "$BOT_SCRIPT"
