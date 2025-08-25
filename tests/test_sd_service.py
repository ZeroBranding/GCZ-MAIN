import unittest
import os
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

# Add project root
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

from services.sd_service import SDService
from core.errors import ConfigError, ExternalToolError

class TestSDService(unittest.TestCase):

    def setUp(self):
        """Set up a temporary workflow file and mock environment."""
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.test_dir.name)
        
        # Create a dummy workflow file
        self.workflows_path = self.test_path / "workflows" / "comfy"
        self.workflows_path.mkdir(parents=True)
        self.workflow_file = self.workflows_path / "sd15_txt2img.json"
        
        # Minimal valid workflow structure
        self.workflow_content = {
            "6": {"inputs": {"text": ""}},
            "7": {"inputs": {"text": ""}},
            "3": {"inputs": {"seed": 0, "steps": 20}},
            "5": {"inputs": {"width": 512, "height": 512}}
        }
        with open(self.workflow_file, 'w') as f:
            json.dump(self.workflow_content, f)

        os.environ['COMFYUI_URL'] = 'mock-api:8188'
        
        # Patch the SDService's workflows_dir to point to our temp dir
        with patch('services.sd_service.Path') as mock_path:
            # This makes Path("workflows/comfy") return our temp path
            type(mock_path.return_value).workflows_dir = self.workflows_path
            self.service = SDService()
            self.service.workflows_dir = self.workflows_path

    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_dir.cleanup()
        del os.environ['COMFYUI_URL']

    def test_txt2img_workflow_not_found(self):
        """Test that ConfigError is raised if the workflow file is missing."""
        os.remove(self.workflow_file)
        with self.assertRaises(ConfigError):
            self.service.txt2img(prompt="a test")

    @patch('services.sd_service.urllib.request.urlopen')
    def test_txt2img_api_call_and_polling(self, mock_urlopen):
        """Test the full txt2img flow with mocked API responses."""
        # --- Mock API responses ---
        # 1. Response for _queue_prompt
        queue_response = MagicMock()
        queue_response.read.return_value = json.dumps({"prompt_id": "123"}).encode()
        
        # 2. Response for _get_history (first incomplete, then complete)
        history_incomplete = MagicMock()
        history_incomplete.read.return_value = json.dumps({"123": {"status": "running"}}).encode()
        
        history_complete = MagicMock()
        history_complete_data = {
            "123": {"outputs": {"9": {"images": [
                {"filename": "test.png", "subfolder": "", "type": "output"}
            ]}}}
        }
        history_complete.read.return_value = json.dumps(history_complete_data).encode()

        # 3. Response for _get_image
        image_response = MagicMock()
        image_response.read.return_value = b"fake_image_bytes"

        # Configure the mock to return responses in order
        mock_urlopen.side_effect = [
            queue_response,
            history_incomplete,
            history_complete,
            image_response
        ]

        result_path_str = self.service.txt2img(prompt="a cat")
        result_path = Path(result_path_str)

        self.assertTrue(result_path.exists())
        self.assertIn("IMG_", result_path.name)
        with open(result_path, 'rb') as f:
            self.assertEqual(f.read(), b"fake_image_bytes")

if __name__ == '__main__':
    unittest.main()
