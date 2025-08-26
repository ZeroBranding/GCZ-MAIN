import unittest
import os
import importlib
from unittest.mock import patch
from pathlib import Path
import sys

# Add project root to the path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import core.env

class TestEnvLoading(unittest.TestCase):

    # We no longer need setUp and tearDown to create a physical file

    @patch('core.env.os.getenv')
    def test_env_loading_and_fallback(self, mock_getenv):
        """
        Tests if core.env correctly loads variables by mocking os.getenv.
        """
        # Configure the mock to return different values based on the key
        def get_env_var(key, default=None):
            test_vars = {
                "GMAIL_USER": "test_user@gmail.com",
                "IMAP_PASS": "imap_password",
                "LOG_LEVEL": "DEBUG",
            }
            return test_vars.get(key, default)

        mock_getenv.side_effect = get_env_var

        # Reload the core.env module to force it to re-read the "environment"
        # provided by our mock
        importlib.reload(core.env)

        # --- Assertions ---
        # 1. Test direct loading
        self.assertEqual(core.env.LOG_LEVEL, "DEBUG")

        # 2. Test fallback mechanism
        self.assertEqual(core.env.EMAIL_USER, "test_user@gmail.com")
        self.assertEqual(core.env.EMAIL_PASS, "imap_password")

        # 3. Test default values
        self.assertEqual(core.env.DEFAULT_MODEL, "llama3:latest")

        # 4. Test boolean flags with default
        self.assertTrue(core.env.SAVE_MEDIA_LOCALLY)

if __name__ == '__main__':
    unittest.main()
