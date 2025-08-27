#!/bin/bash
#
# This script downloads the external dependencies required by the project.
# It clones the git repositories into the external/ directory.
#
# This approach is used instead of Git submodules to work around
# limitations in the development environment.

set -e

echo "Downloading external dependencies..."

# Get the root directory of the repository
REPO_ROOT=$(git rev-parse --show-toplevel)
EXTERNAL_DIR="$REPO_ROOT/external"

# Ensure the external directory exists
mkdir -p "$EXTERNAL_DIR"

# --- Dependencies to clone ---
# Format: "repo_url destination_directory_name"
dependencies=(
    "https://github.com/ltdrdata/ComfyUI-Manager ComfyUI-Manager"
    "https://github.com/myshell-ai/OpenVoice OpenVoice"
    "https://github.com/hzwer/Practical-RIFE RIFE"
    "https://github.com/Rudrabha/Wav2Lip Wav2Lip"
    "https://github.com/coqui-ai/TTS XTTS"
    "https://github.com/baresip/baresip baresip"
)

# --- Clean up and clone all repositories ---
for dep in "${dependencies[@]}"; do
    # Split the string into url and dir_name
    read -r url dir_name <<<"$dep"

    target_path="$EXTERNAL_DIR/$dir_name"

    echo "--- Processing $dir_name ---"

    if [ -d "$target_path" ]; then
        echo "Removing existing directory: $target_path"
        rm -rf "$target_path"
    fi

    echo "Cloning $url into $target_path..."
    git clone --depth 1 "$url" "$target_path"
    echo
done

echo "All external dependencies downloaded successfully."
