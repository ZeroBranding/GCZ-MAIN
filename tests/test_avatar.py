import os

# Add project root to path to allow direct script execution
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parent.parent))

from services.avatar_service import AvatarService


class TestAvatarService(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory structure for testing."""
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.test_dir.name)

        # Create dummy repo and checkpoint directories
        self.sadtalker_path = self.test_path / "SadTalker"
        self.realesrgan_path = self.test_path / "Real-ESRGAN"
        (self.sadtalker_path / "checkpoints").mkdir(parents=True)
        (self.realesrgan_path / "weights").mkdir(parents=True)

        # Create dummy model files
        (self.sadtalker_path / "checkpoints" / "SadTalker_V0.0.2_512.safetensors").touch()
        (self.sadtalker_path / "checkpoints" / "mapping_00229-model.pth.tar").touch()
        (self.sadtalker_path / "checkpoints" / "Wav2Lip_original.pth").touch()
        (self.realesrgan_path / "weights" / "RealESRGAN_x4plus.pth").touch()

        # Create dummy input files
        self.image_path = self.test_path / "test_image.png"
        self.wav_path = self.test_path / "test_audio.wav"
        self.image_path.touch()
        self.wav_path.touch()

        self.service = AvatarService(
            sadtalker_repo_path=str(self.sadtalker_path),
            realesrgan_repo_path=str(self.realesrgan_path)
        )

    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_dir.cleanup()

    @patch('services.avatar_service.logger')
    def test_ensure_checkpoints_success(self, mock_logger):
        """Test that checkpoint validation passes when all files exist."""
        result = self.service.ensure_checkpoints()
        self.assertTrue(result)
        mock_logger.info.assert_called_with("All required model checkpoints are present.")

    @patch('services.avatar_service.logger')
    def test_ensure_checkpoints_failure(self, mock_logger):
        """Test that checkpoint validation fails when a file is missing."""
        os.remove(self.sadtalker_path / "checkpoints" / "Wav2Lip_original.pth")
        result = self.service.ensure_checkpoints()
        self.assertFalse(result)
        # Check that a warning was logged for the missing file
        self.assertTrue(any("Wav2Lip_original.pth" in call.args[0] for call in mock_logger.warning.call_args_list))

    @patch('services.avatar_service.subprocess.run')
    @patch('services.avatar_service.logger')
    def test_render_dry_run(self, mock_logger, mock_subprocess_run):
        """Test the render method in dry-run mode."""
        result = self.service.render(
            image_path=str(self.image_path),
            wav_path=str(self.wav_path),
            dry_run=True
        )

        self.assertEqual(result, "dry_run_success")

        # Verify that subprocess.run was NOT called
        mock_subprocess_run.assert_not_called()

        # Verify that the commands were logged
        log_calls = [call.args[0] for call in mock_logger.info.call_args_list]

        # Check for SadTalker command components
        self.assertTrue(any("Running SadTalker" in log for log in log_calls))
        self.assertTrue(any(f"inference.py --driven_audio {self.wav_path}" in log for log in log_calls))

        # Check for Real-ESRGAN command components
        self.assertTrue(any("Running Real-ESRGAN" in log for log in log_calls))
        self.assertTrue(any("inference_realesrgan_video.py -i" in log for log in log_calls))

        # Check for ffmpeg command components
        self.assertTrue(any("Running ffmpeg" in log for log in log_calls))
        self.assertTrue(any(f"-i {self.wav_path}" in log for log in log_calls))


if __name__ == '__main__':
    unittest.main()
