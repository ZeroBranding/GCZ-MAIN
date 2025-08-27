#!/bin/bash
#
# Setup script for the GCZ-MAIN project on Linux and macOS.
#
# This script performs the following actions:
# 1. Installs Python dependencies.
# 2. Downloads external models and code.
# 3. Creates a default .env file from the sample.

set -e

echo "--- Setting up GCZ-MAIN ---"

# --- Step 1: Install Python Dependencies ---
echo "Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt
echo "Dependencies installed."
echo

# --- Step 2: Download External Dependencies ---
echo "Downloading external dependencies..."
# Ensure the download script is executable, just in case.
chmod +x scripts/download_dependencies.sh
# Run the script
./scripts/download_dependencies.sh
echo "External dependencies downloaded."
echo

# --- Step 3: Create .env file ---
if [ ! -f .env ]; then
    echo "Creating .env file from .env.sample..."
    cp .env.sample .env
    echo ".env file created. Please review and edit it with your credentials."
else
    echo ".env file already exists. Skipping creation."
fi
echo

echo "--- Setup complete! ---"
echo "You can now run the application using the appropriate run script (e.g., run.sh or by running the services directly)."
