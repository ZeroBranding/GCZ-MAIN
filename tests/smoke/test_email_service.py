import unittest
from unittest.mock import patch, MagicMock
import os
import imaplib
import sys
import importlib
from pathlib import Path

# Add project root to the path to allow imports from services, core, etc.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# It's better to import the class to be tested directly
from services.email_service import EmailService, ConfigError, ExternalToolError
import core.env

class TestEmailServiceSmoke(unittest.TestCase):

    @patch.dict(os.environ, {"GMAIL_USER": "test@example.com", "GMAIL_PASS": "password"})
    @patch('services.email_service.load_config')
    def test_successful_initialization(self, mock_load_config):
        """
        Test that the EmailService initializes correctly when env vars are set.
        """
        # Mock the config loaded from YAML
        mock_config_data = {
            'imap_host': 'imap.example.com',
            'smtp_host': 'smtp.example.com',
            'smtp_port': 587
        }
        # The structure is nested, so we mock the result of getattr
        mock_account_config = MagicMock()
        mock_account_config.__getitem__.side_effect = mock_config_data.__getitem__

        mock_config = MagicMock()
        type(mock_config).gmail = mock_account_config

        mock_load_config.return_value = mock_config

        # Reload core.env to pick up the patched environment variables
        importlib.reload(core.env)

        try:
            service = EmailService('gmail')
            self.assertIsNotNone(service)
            self.assertEqual(service.email_user, "test@example.com")
        except ConfigError:
            self.fail("EmailService initialization failed with valid config")

    @patch('services.email_service.load_config')
    def test_initialization_fails_without_env_vars(self, mock_load_config):
        """
        Test that EmailService raises ConfigError if environment variables are missing.
        """
        # Ensure the environment variables are not set for this test
        if "GMAIL_USER" in os.environ:
            del os.environ["GMAIL_USER"]
        if "GMAIL_PASS" in os.environ:
            del os.environ["GMAIL_PASS"]

        with self.assertRaises(ConfigError):
            EmailService('gmail')

    @patch.dict(os.environ, {"GMAIL_USER": "test@example.com", "GMAIL_PASS": "password"})
    @patch('services.email_service.load_config')
    @patch('imaplib.IMAP4_SSL')
    def test_list_unread_emails_handles_connection_error(self, mock_imap_ssl, mock_load_config):
        """
        Test that list_unread_emails returns an empty list when IMAP connection fails.
        """
        # Mock the config
        mock_config_data = {
            'imap_host': 'imap.example.com',
            'smtp_host': 'smtp.example.com',
            'smtp_port': 587
        }
        mock_account_config = MagicMock()
        mock_account_config.__getitem__.side_effect = mock_config_data.__getitem__
        mock_config = MagicMock()
        type(mock_config).gmail = mock_account_config
        mock_load_config.return_value = mock_config

        # Configure the mock IMAP4_SSL to raise an error on login
        mock_imap_instance = MagicMock()
        mock_imap_instance.login.side_effect = imaplib.IMAP4.error("Login failed")
        mock_imap_ssl.return_value = mock_imap_instance

        # Reload core.env to pick up the patched environment variables
        importlib.reload(core.env)

        # Initialize the service and call the method
        service = EmailService('gmail')
        unread_emails = service.list_unread_emails()

        # Assert that the method returned an empty list and did not crash
        self.assertEqual(unread_emails, [])

        # Optional: Check if the error was logged (requires mocking the logger)
        # For a smoke test, checking the return value is sufficient.

if __name__ == '__main__':
    unittest.main()
