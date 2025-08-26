import os
import pickle

import core.env
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def upload_to_youtube(video_path: str, title: str, description: str, tags: list, privacy: str = "unlisted") -> str:
    """
    Uploads a video to YouTube.

    Args:
        video_path (str): Path to the video file.
        title (str): The title of the video.
        description (str): The description of the video.
        tags (list): A list of tags for the video.
        privacy (str, optional): The privacy status of the video. 
                                 Can be 'public', 'private', or 'unlisted'. Defaults to "unlisted".

    Returns:
        str: The ID of the uploaded video, or None if the upload failed.
    """
    CLIENT_SECRETS_FILE = core.env.YOUTUBE_CLIENT_SECRETS_FILE
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    API_SERVICE_NAME = "youtube"
    API_VERSION = "v3"

    credentials = None
    token_pickle_path = "token.json"

    # Load credentials from file if they exist
    if os.path.exists(token_pickle_path):
        with open(token_pickle_path, "rb") as token:
            credentials = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in.
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(token_pickle_path, "wb") as token:
            pickle.dump(credentials, token)

    try:
        service = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "22"  # Default to "People & Blogs"
            },
            "status": {
                "privacyStatus": privacy,
            },
        }

        # Call the API to upload the video.
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = service.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )

        response = request.execute()
        print(f"Video uploaded successfully! Video ID: {response['id']}")
        return response["id"]
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

if __name__ == '__main__':
    # Example Usage:
    # Ensure you have a 'client_secret.json' file from the Google Cloud Console
    # and a video file at 'test_video.mp4'.
    # Set the YOUTUBE_CLIENT_SECRETS_FILE environment variable if your file has a different name.

    # Create a dummy video file for testing if it doesn't exist
    if not os.path.exists("test_video.mp4"):
        with open("test_video.mp4", "wb") as f:
            f.write(os.urandom(1024 * 1024)) # 1MB dummy file

    video_id = upload_to_youtube(
        video_path="test_video.mp4",
        title="Test Title",
        description="This is a test description.",
        tags=["test", "upload"],
        privacy="private"
    )

    if video_id:
        print(f"Find your video at: https://www.youtube.com/watch?v={video_id}")
    else:
        print("Upload failed.")
