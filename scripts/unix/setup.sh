#!/bin/bash
set -e

# --- Configuration ---
VENV_DIR=".venv"
REQUIREMENTS_FILE="requirements.txt"
PYTHON_VERSION_MIN="3.10"

# --- Helper Functions ---
info() {
    echo "[INFO] $1"
}

warn() {
    echo "[WARN] $1"
}

error() {
    echo "[ERROR] $1" >&2
    exit 1
}

# --- Pre-flight Checks ---
info "Starting setup..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    error "Python 3 is not installed. Please install it before running this script."
fi

# Check Python version
PYTHON_VERSION_CURRENT=$(python3 --version 2>&1 | awk '{print $2}')
if ! printf '%s\n' "$PYTHON_VERSION_MIN" "$PYTHON_VERSION_CURRENT" | sort -V -C; then
    warn "Current Python version is $PYTHON_VERSION_CURRENT, but >= $PYTHON_VERSION_MIN is recommended."
fi

# --- Virtual Environment Setup ---
if [ -d "$VENV_DIR" ]; then
    info "Virtual environment '$VENV_DIR' already exists."
else
    info "Creating Python virtual environment in '$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
fi

# Activate the virtual environment
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
info "Virtual environment activated."

# --- Dependency Installation ---
if [ -f "$REQUIREMENTS_FILE" ]; then
    info "Installing dependencies from '$REQUIREMENTS_FILE'..."
    pip install -r "$REQUIREMENTS_FILE"
    info "Dependencies installed successfully."
else
    error "Could not find '$REQUIREMENTS_FILE'. Please ensure the file exists in the root directory."
fi

# --- Hardware Checks (Non-blocking) ---
info "Performing hardware checks..."

# Check for NVIDIA GPU and CUDA
if command -v nvidia-smi &> /dev/null; then
    info "NVIDIA GPU detected."
    info "CUDA Version: $(nvidia-smi --query-gpu=driver_version,cuda_version.raw --format=csv,noheader,nounits)"
else
    info "No NVIDIA GPU detected with nvidia-smi. Some features may be unavailable or run on CPU."
fi

info "Setup complete. To activate the environment, run: source $VENV_DIR/bin/activate"
