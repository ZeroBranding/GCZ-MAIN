import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from core.errors import ExternalToolError
from core.logging import logger

# Path to the uploader script relative to the project root
TIKTOK_UPLOADER_CLI_PATH = Path("external") / "TikTokAutoUploader" / "cli.py"

def check_tiktok_login(profile: str = "default") -> bool:
    """
    Checks if the specified TikTok profile is logged in by running the status command.
    """
    if not TIKTOK_UPLOADER_CLI_PATH.exists():
        raise FileNotFoundError(
            f"TikTok uploader script not found at: {TIKTOK_UPLOADER_CLI_PATH}"
        )

    command = [
        sys.executable,
        str(TIKTOK_UPLOADER_CLI_PATH),
        "status",
        "-n", profile,
    ]

    try:
        logger.info(f"Checking TikTok login status for profile '{profile}'...")
        result = subprocess.run(command, capture_output=True, text=True, check=False)

        # The 'status' command is not well-documented. We'll check for a non-zero exit code
        # or specific error messages that indicate a login problem.
        if result.returncode != 0:
            logger.warning(
                f"TikTok login check for '{profile}' returned non-zero "
                f"exit code. Stderr: {result.stderr}"
            )
            return False

        # A more robust check could parse stdout, e.g., for "Not logged in".
        if ("not logged in" in result.stdout.lower() or
                "no profiles found" in result.stdout.lower()):
             logger.warning(f"TikTok profile '{profile}' is not logged in.")
             return False

        logger.info(f"TikTok profile '{profile}' appears to be logged in.")
        return True

    except (subprocess.SubprocessError, FileNotFoundError) as e:
        raise ExternalToolError(f"Failed to execute TikTok login check: {e}")

def upload_to_tiktok(video_path: str, caption: str, profile: str = "default") -> Dict[str, Any]:
    """
    Uploads a video to TikTok using the external CLI, with robust error handling.
    """
    video_path_obj = Path(video_path)
    if not video_path_obj.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if not TIKTOK_UPLOADER_CLI_PATH.exists():
        raise FileNotFoundError(
            f"TikTok uploader script not found at: {TIKTOK_UPLOADER_CLI_PATH}"
        )

    if not check_tiktok_login(profile):
        raise ExternalToolError(
            f"TikTok profile '{profile}' is not logged in. Please run "
            f"'python {TIKTOK_UPLOADER_CLI_PATH} login -n {profile}' manually."
        )

    command = [
        sys.executable,
        str(TIKTOK_UPLOADER_CLI_PATH),
        "upload",
        "-n", profile,
        "-v", str(video_path_obj.resolve()),
        "-t", caption,
    ]

    logger.info(f"Executing TikTok upload: {' '.join(command)}")
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8')

        if result.returncode != 0:
            error_message = result.stderr or result.stdout
            logger.error(
                f"TikTok upload failed with exit code {result.returncode}. "
                f"Error: {error_message}"
            )
            raise ExternalToolError(
                f"TikTok upload script failed: {error_message}"
            )

        # Assuming success if the command returns 0. A more robust solution
        # would parse stdout for a video ID or URL.
        logger.info(f"TikTok upload command completed. Stdout: {result.stdout}")
        return {
            "ok": True,
            "id": "unknown",  # The script does not easily provide the video ID
            "message": result.stdout
        }

    except (subprocess.SubprocessError, FileNotFoundError) as e:
        raise ExternalToolError(f"Failed to execute TikTok upload subprocess: {e}")

if __name__ == '__main__':
    # Example Usage:
    # 1. Make sure you have cloned TikTokAutoUploader into the 'external' directory.
    # 2. Log in via the command line first:
    #    python external/TikTokAutoUploader/cli.py login -n default
    # 3. Have a 'test_video.mp4' in the same directory.

    # Create a dummy video file for testing if it doesn't exist
    if not os.path.exists("test_video.mp4"):
        with open("test_video.mp4", "wb") as f:
            f.write(os.urandom(1024 * 1024 * 3)) # 3MB dummy video file

    try:
        success = upload_to_tiktok(
            video_path="test_video.mp4",
            caption="My awesome test video for TikTok! #test #automation"
        )

        if success["ok"]:
            print("TikTok upload process completed successfully.")
            print(f"Video ID: {success['id']}")
            print(f"Message: {success['message']}")
        else:
            print("TikTok upload process failed.")
            print(f"Error: {success['message']}")

    except ExternalToolError as e:
        print(f"An error occurred during TikTok upload: {e}")
