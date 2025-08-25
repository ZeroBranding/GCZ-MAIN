import unittest
import os
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

# Add project root
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

from services.anim_service import AnimService
from core.errors import ConfigError

class TestAnimService(unittest.TestCase):

    def setUp(self):
        """Set up a temporary workflow file and mock environment."""
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.test_dir.name)

        # Create dummy workflow file
        self.workflows_path = self.test_path / "workflows" / "comfy"
        self.workflows_path.mkdir(parents=True)
        self.workflow_file = self.workflows_path / "animatediff.json"
        self.workflow_content = {"6": {"inputs": {"text": ""}}}
        with open(self.workflow_file, 'w') as f:
            json.dump(self.workflow_content, f)

        os.environ['COMFYUI_URL'] = 'mock-api:8188'
        os.environ['PATH_FFMPEG'] = 'mock-ffmpeg'

        # Patch the AnimService's workflows_dir
        with patch('services.sd_service.Path') as mock_path:
            type(mock_path.return_value).workflows_dir = self.workflows_path
            self.service = AnimService()
            self.service.workflows_dir = self.workflows_path

    def tearDown(self):
        """Clean up the temporary directory and environment."""
        self.test_dir.cleanup()
        del os.environ['COMFYUI_URL']
        del os.environ['PATH_FFMPEG']

    def test_plan_animation_valid(self):
        """Test that a valid animation plan is created correctly."""
        plan = self.service.plan_animation(prompt="test", seconds=2, fps=10)
        self.assertEqual(plan['frame_count'], 20)
        self.assertEqual(plan['prompt'], "test")

    def test_plan_animation_invalid_bounds(self):
        """Test that planning raises ValueError for out-of-bounds parameters."""
        with self.assertRaises(ValueError):
            self.service.plan_animation(prompt="test", seconds=11)
        with self.assertRaises(ValueError):
            self.service.plan_animation(prompt="test", fps=5)

    @patch('services.anim_service.subprocess.run')
    @patch('services.sd_service.SDService._get_image', return_value=b'fake_frame')
    @patch('services.sd_service.SDService._get_history')
    @patch('services.sd_service.SDService._queue_prompt', return_value='prompt-123')
    def test_render_animation_dry_run(self, mock_queue, mock_history, mock_get_image, mock_subprocess):
        """Test the render_animation flow, mocking API calls and ffmpeg."""
        # Mock history to return a successful result immediately
        mock_history.return_value = {
            "prompt-123": {"outputs": {"1": {"images": [
                {"filename": f, "subfolder": "", "type": "output"}
                for f in ["f1.png", "f2.png"]
            ]}}}
        }
        
        plan = self.service.plan_animation(prompt="test render", seconds=1, fps=2)
        result_path_str = self.service.render_animation(plan)
        result_path = Path(result_path_str)

        # Verify API calls
        mock_queue.assert_called_once()
        self.assertEqual(mock_get_image.call_count, 2)

        # Verify ffmpeg call
        mock_subprocess.assert_called_once()
        ffmpeg_command = mock_subprocess.call_args[0][0]
        self.assertIn('mock-ffmpeg', ffmpeg_command[0])
        self.assertIn('2', ffmpeg_command) # FPS
        self.assertTrue(ffmpeg_command[-1].endswith('out.mp4'))

        # Check that the final output path is correct
        self.assertEqual(result_path.name, 'out.mp4')
        self.assertTrue(result_path.parent.is_dir())

if __name__ == '__main__':
    unittest.main()
