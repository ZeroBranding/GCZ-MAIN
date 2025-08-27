import os

from core.config import get_settings
from instagrapi import Client
from instagrapi.exceptions import LoginRequired


def get_instagram_client():
    """
    Initializes and returns an instagrapi client.
    Logs in using credentials from environment variables.
    """
    settings = get_settings()
    username = settings.app.IG_USERNAME
    password = settings.app.IG_PASSWORD

    if not username or not password:
        raise ValueError("IG_USERNAME and IG_PASSWORD environment variables must be set.")

    cl = Client()

    # Path for session cache
    session_file = f"{username}.json"

    if os.path.exists(session_file):
        cl.load_settings(session_file)
        print("Loaded session from file.")
        try:
            cl.login(username, password)
        except LoginRequired:
            print("Session is invalid, re-logging in.")
            # If session is invalid, remove it and login again
            os.remove(session_file)
            cl.login(username, password)
            cl.dump_settings(session_file)
    else:
        print("No session file found, logging in.")
        cl.login(username, password)
        cl.dump_settings(session_file)

    return cl

def upload_to_instagram_video(video_path: str, caption: str) -> str:
    """
    Uploads a video to Instagram Reels.

    Args:
        video_path (str): Path to the video file.
        caption (str): The caption for the video.

    Returns:
        str: The media ID of the uploaded video, or None if failed.
    """
    try:
        cl = get_instagram_client()
        media = cl.video_upload(video_path, caption=caption)
        print(f"Video uploaded successfully to Instagram! Media ID: {media.pk}")
        return media.pk
    except Exception as e:
        print(f"An error occurred while uploading video to Instagram: {e}")
        return None

def upload_to_instagram_photo(image_path: str, caption: str) -> str:
    """
    Uploads a photo to Instagram.

    Args:
        image_path (str): Path to the image file.
        caption (str): The caption for the photo.

    Returns:
        str: The media ID of the uploaded photo, or None if failed.
    """
    try:
        cl = get_instagram_client()
        media = cl.photo_upload(image_path, caption=caption)
        print(f"Photo uploaded successfully to Instagram! Media ID: {media.pk}")
        return media.pk
    except Exception as e:
        print(f"An error occurred while uploading photo to Instagram: {e}")
        return None

if __name__ == '__main__':
    # Example Usage:
    # 1. Set environment variables:
    #    export IG_USERNAME="your_instagram_username"
    #    export IG_PASSWORD="your_instagram_password"
    # 2. Have 'test_video.mp4' and 'test_image.jpg' in the same directory.

    # Create dummy files for testing if they don't exist
    if not os.path.exists("test_video.mp4"):
        with open("test_video.mp4", "wb") as f:
            f.write(os.urandom(1024 * 1024 * 2)) # 2MB dummy video file

    if not os.path.exists("test_image.jpg"):
        from PIL import Image
        img = Image.new('RGB', (100, 100), color = 'red')
        img.save('test_image.jpg')

    # Example video upload
    video_media_id = upload_to_instagram_video(
        video_path="test_video.mp4",
        caption="Check out this amazing video! #test #instagrapi"
    )
    if video_media_id:
        print(f"Video upload successful. Media ID: {video_media_id}")
    else:
        print("Video upload failed.")

    # Example photo upload
    photo_media_id = upload_to_instagram_photo(
        image_path="test_image.jpg",
        caption="Here's a test photo. #test #instagrapi"
    )
    if photo_media_id:
        print(f"Photo upload successful. Media ID: {photo_media_id}")
    else:
        print("Photo upload failed.")
