import os
import unittest
from pathlib import Path


class TestConfigValidation(unittest.TestCase):

    def setUp(self):
        """Set up the base directory for the tests."""
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.configs_dir = self.base_dir / "configs"

    def test_all_required_configs_exist(self):
        """
        Validates that all expected .yml configuration files are present.
        """
        required_configs = [
            "avatar.yml",
            "email.yml",
            "phone.yml",
            "routing.yml",
            "sd.yml",
            "telegram.yml"
        ]

        missing_configs = []
        for config_file in required_configs:
            config_path = self.configs_dir / config_file
            if not config_path.is_file():
                missing_configs.append(config_file)

        self.assertEqual(
            len(missing_configs),
            0,
            f"The following required configuration files are missing: {', '.join(missing_configs)}"
        )

    def test_no_empty_config_files(self):
        """
        Checks that configuration files are not empty.
        """
        config_files = list(self.configs_dir.glob("*.yml"))
        empty_files = []

        for config_path in config_files:
            if os.path.getsize(config_path) == 0:
                empty_files.append(config_path.name)

        self.assertEqual(
            len(empty_files),
            0,
            f"The following configuration files are empty: {', '.join(empty_files)}"
        )


if __name__ == '__main__':
    unittest.main()
