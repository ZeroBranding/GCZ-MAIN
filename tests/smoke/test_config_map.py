import unittest
import os
from pathlib import Path
import sys
import yaml
from pydantic import BaseModel

# Add project root to the path to allow imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.config import load_config, load_yaml

# --- Test Pydantic Model ---
class TestAppConfig(BaseModel):
    app_name: str
    version: float
    debug_mode: bool

class TestConfigMapping(unittest.TestCase):

    def setUp(self):
        """Create a dummy config.yml file for testing."""
        self.config_dir = Path("configs")
        self.config_dir.mkdir(exist_ok=True)
        self.test_yaml_path = self.config_dir / "test_app.yml"

        self.test_data = {
            "app_name": "TestRunner",
            "version": 1.2,
            "debug_mode": True
        }

        with open(self.test_yaml_path, "w") as f:
            yaml.dump(self.test_data, f)

    def tearDown(self):
        """Remove the dummy config file and directory."""
        if os.path.exists(self.test_yaml_path):
            os.remove(self.test_yaml_path)
        # Check if directory is empty before removing
        if os.path.exists(self.config_dir) and not os.listdir(self.config_dir):
             os.rmdir(self.config_dir)


    def test_load_yaml_successfully(self):
        """Tests that the raw YAML loading function works."""
        loaded_data = load_yaml("test_app")
        self.assertEqual(loaded_data, self.test_data)

    def test_load_config_with_pydantic_validation(self):
        """
        Tests that load_config correctly loads a YAML file and validates
        it against a Pydantic model.
        """
        # Call the function to be tested
        config_object = load_config("test_app", TestAppConfig)

        # --- Assertions ---
        # 1. Check if the returned object is of the correct type
        self.assertIsInstance(config_object, TestAppConfig)

        # 2. Check if the attributes match the data from the YAML file
        self.assertEqual(config_object.app_name, "TestRunner")
        self.assertEqual(config_object.version, 1.2)
        self.assertTrue(config_object.debug_mode)

if __name__ == '__main__':
    unittest.main()
