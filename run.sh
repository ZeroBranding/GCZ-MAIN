#!/bin/bash
#
# Run script for the GCZ-MAIN project on Linux and macOS.
#
# This script performs the following actions:
# 1. Starts the ComfyUI service in the background.
# 2. Starts the Email Poller service in the background.
# 3. Starts the Telegram Bot in the foreground.

set -e

echo "--- Starting GCZ-MAIN Services ---"

# --- Create logs directory if it doesn't exist ---
mkdir -p logs

# --- 1. Start ComfyUI Service ---
COMFYUI_DIR="external/ComfyUI-Manager"
if [ -d "$COMFYUI_DIR" ]; then
    echo "Starting ComfyUI service in the background..."
    (cd "$COMFYUI_DIR" && python main.py > ../../logs/comfyui.log 2>&1 &)
    echo "ComfyUI service started. Logs are in logs/comfyui.log"
else
    echo "Warning: ComfyUI directory not found at $COMFYUI_DIR. Skipping."
fi
echo

# --- 2. Start Email Poller Service ---
echo "Starting Email Poller service in the background..."
(python -m services.email_poller >> logs/email_poller.log 2>&1 &)
echo "Email Poller service started. Logs are in logs/email_poller.log"
echo

# --- 3. Start Telegram Bot ---
echo "Starting Telegram Bot in the foreground..."
echo "Press CTRL+C to stop the bot."
python telegram_bot.py

# --- Cleanup on exit ---
# When the Telegram bot is stopped, kill the background jobs.
echo
echo "Telegram Bot stopped. Cleaning up background services..."
# The 'jobs -p' command lists the PIDs of background jobs.
# The '-' before the PID in kill sends the signal to the entire process group.
kill -TERM -- -$(jobs -p) 2>/dev/null
echo "All services stopped."
