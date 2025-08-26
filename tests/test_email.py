import email
import os

# Den `services`-Pfad zum Systempfad hinzufügen, um den Import zu ermöglichen
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from services.email_service import EmailService


@patch('services.email_service.get_settings')
class TestEmailService(unittest.TestCase):

    def setUp(self, mock_get_settings):
        """Set up a temporary directory and mock environment for testing."""
        # Mock the settings object
        mock_settings = MagicMock()
        mock_settings.app.EMAIL_USER = "testuser@gmail.com"
        mock_settings.app.EMAIL_PASS = "testpass"
        mock_settings.email.gmail.imap_host = "imap.gmail.com"
        mock_settings.email.gmail.smtp_host = "smtp.gmail.com"
        mock_settings.email.gmail.smtp_port = 587
        mock_get_settings.return_value = mock_settings

        self.service = EmailService('gmail')
        self.test_drafts_dir = self.service.drafts_dir
        self.test_drafts_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up environment variables and temporary files."""
        # Stop the patcher
        self.load_config_patcher.stop()

        # Clean up environment variables
        del os.environ['TEST_GMAIL_USER']
        del os.environ['TEST_GMAIL_PASS']

        # Clean up any created draft files
        for item in self.test_drafts_dir.iterdir():
            item.unlink()
        if self.test_drafts_dir.exists():
            self.test_drafts_dir.rmdir()

    @patch('services.email_service.EmailService.fetch_email')
    def test_draft_reply_dry_run(self, mock_fetch_email):
        """
        Testet das Erstellen eines Antwortentwurfs aus einer .eml-Fixture.
        """
        # Mock `fetch_email`, um den Inhalt der lokalen .eml-Datei zurückzugeben
        mock_fetch_email.return_value = self.eml_content

        original_email_id = '123'
        reply_body = "Das ist die Testantwort auf die Fixture-E-Mail."

        # Führt die zu testende Methode aus
        draft = self.service.draft_reply(original_email_id, reply_body, dry_run=True)

        # Überprüfungen
        self.assertIsNotNone(draft)
        self.assertIn('draft_id', draft)
        self.assertIn('content', draft)

        # Parsen des MIME-Inhalts, um die Struktur zu überprüfen
        draft_msg = email.message_from_string(draft['content'])

        self.assertEqual(draft_msg['To'], '"Sender Name" <sender@example.com>')
        self.assertEqual(draft_msg['From'], 'testuser@gmail.com')
        self.assertTrue(draft_msg['Subject'].startswith('Re:'))

        # Überprüfen, ob der Antworttext im Body enthalten ist
        self.assertTrue(draft_msg.is_multipart())
        payload = draft_msg.get_payload(0).get_payload(decode=True).decode()
        self.assertIn(reply_body, payload)

        # Sicherstellen, dass die ursprüngliche Methode aufgerufen wurde
        mock_fetch_email.assert_called_once_with(original_email_id)

if __name__ == '__main__':
    unittest.main()
