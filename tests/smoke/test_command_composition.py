import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Mock the services before they are imported by telegram_service
# This is crucial to prevent real service initializations
mock_sd_service = MagicMock()
mock_anim_service = MagicMock()
mock_avatar_service = MagicMock()
mock_youtube_service = MagicMock()
mock_instagram_service = MagicMock()
mock_tiktok_service = MagicMock()

# --- Create a dummy configuration for email service to avoid errors ---
mock_email_service = MagicMock()
mock_email_service.list_unread_emails.return_value = []


modules = {
    'services.sd_service.SDService': mock_sd_service,
    'services.anim_service.AnimService': mock_anim_service,
    'services.avatar_service.AvatarService': mock_avatar_service,
    'services.youtube_service.YoutubeService': mock_youtube_service,
    'services.instagram_service.InstagramService': mock_instagram_service,
    'services.tiktok_service.TikTokService': mock_tiktok_service,
    'services.email_service.EmailService': mock_email_service
}

with patch.dict('sys.modules', modules):
    from services import telegram_service

class TestCommandComposition(unittest.TestCase):

    def setUp(self):
        self.update = AsyncMock()
        self.context = AsyncMock()
        self.context.args = []

    def test_img_command_sends_prompt_to_service(self):
        """Ensure /img command passes the prompt correctly."""
        self.context.args = ["a", "test", "prompt"]
        prompt = "a test prompt"
        mock_sd_service.return_value.txt2img.return_value = "path/to/image.png"

        # We need to run the async function in an event loop
        asyncio.run(telegram_service.img_command(self.update, self.context))

        mock_sd_service.return_value.txt2img.assert_called_once_with(prompt)
        self.update.message.reply_text.assert_called_with(f"Bild wird für Prompt generiert: '{prompt}'...")

    def test_anim_command_parses_args_correctly(self):
        """Ensure /anim command parses arguments and calls the service."""
        self.context.args = ['"a cool prompt"|10|24']
        prompt, sec, fps = "a cool prompt", 10, 24
        mock_anim_service.return_value.animate.return_value = "path/to/video.mp4"

        asyncio.run(telegram_service.anim_command(self.update, self.context))

        mock_anim_service.return_value.animate.assert_called_once_with(prompt, sec, fps)
        self.update.message.reply_text.assert_called_with(f"Animation wird für Prompt generiert: '{prompt}' ({sec}s @ {fps}fps)...")

    def test_avatar_requires_reply_to_photo(self):
        """Ensure /avatar command checks for a replied-to photo."""
        self.update.message.reply_to_message = None

        asyncio.run(telegram_service.avatar_command(self.update, self.context))

        self.update.message.reply_text.assert_called_with("Bitte antworten Sie auf ein Bild, um diesen Befehl zu verwenden.")

    def test_upload_commands_require_reply(self):
        """Ensure upload commands check for a replied-to message."""
        self.update.message.reply_to_message = None

        asyncio.run(telegram_service.yt_upload_command(self.update, self.context))
        self.update.message.reply_text.assert_called_with("Bitte antworten Sie auf ein Video oder Bild, um es auf YouTube hochzuladen.")

        asyncio.run(telegram_service.ig_upload_command(self.update, self.context))
        self.update.message.reply_text.assert_called_with("Bitte antworten Sie auf ein Video oder Bild, um es auf Instagram hochzuladen.")

        asyncio.run(telegram_service.tt_upload_command(self.update, self.context))
        self.update.message.reply_text.assert_called_with("Bitte antworten Sie auf ein Video oder Bild, um es auf TikTok hochzuladen.")


if __name__ == '__main__':
    unittest.main()
