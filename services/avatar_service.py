import shutil
import subprocess
import tempfile
from pathlib import Path

from core.logging import logger

# --- Constants ---
BASE_DIR = Path(__file__).resolve().parent.parent
SADTALKER_DIR = BASE_DIR / "external" / "SadTalker"
REALESRGAN_DIR = BASE_DIR / "external" / "Real-ESRGAN"
FFMPEG_PATH = "ffmpeg"  # Assuming ffmpeg is in the system's PATH

class AvatarService:
    def __init__(self, sadtalker_repo_path=None, realesrgan_repo_path=None):
        self.sadtalker_dir = Path(sadtalker_repo_path) if sadtalker_repo_path else SADTALKER_DIR
        self.realesrgan_dir = Path(realesrgan_repo_path) if realesrgan_repo_path else REALESRGAN_DIR

        self.sadtalker_checkpoints = self.sadtalker_dir / "checkpoints"
        self.realesrgan_weights = self.realesrgan_dir / "weights"

        logger.info(f"AvatarService initialized with SadTalker path: {self.sadtalker_dir}")
        logger.info(f"AvatarService initialized with Real-ESRGAN path: {self.realesrgan_dir}")

    def ensure_checkpoints(self):
        """
        Checks if the required model checkpoints for SadTalker and Real-ESRGAN exist.
        Logs warnings if they are missing.
        """
        missing_files = []

        # SadTalker checkpoints
        sadtalker_models = [
            "SadTalker_V0.0.2_512.safetensors",
            "mapping_00229-model.pth.tar",
            "Wav2Lip_original.pth",
        ]
        for model in sadtalker_models:
            if not (self.sadtalker_checkpoints / model).exists():
                missing_files.append(f"SadTalker: {model}")

        # Real-ESRGAN weights
        realesrgan_model = "RealESRGAN_x4plus.pth"
        if not (self.realesrgan_weights / realesrgan_model).exists():
            missing_files.append(f"Real-ESRGAN: {realesrgan_model}")

        if missing_files:
            logger.warning("The following model files are missing:")
            for file in missing_files:
                logger.warning(f"- {file}")
            logger.warning("Please run the 'get_sadtalker_models.ps1' and 'get_realesrgan_models.ps1' scripts.")
            return False

        logger.info("All required model checkpoints are present.")
        return True

    def render(self, image_path: str, wav_path: str, fps: int = 30, dry_run: bool = False):
        """
        Generates a talking head video using SadTalker, upscales it with Real-ESRGAN,
        and muxes the audio.
        
        Args:
            image_path (str): Path to the source image.
            wav_path (str): Path to the source audio file.
            fps (int): Frames per second for the output video.
            dry_run (bool): If True, only logs the commands that would be executed.
            
        Returns:
            str: The path to the final MP4 file, or None on failure.
        """
        if not self.ensure_checkpoints():
            return None

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # --- 1. Run SadTalker ---
            sadtalker_output_video = temp_dir_path / "sadtalker_output.mp4"
            sadtalker_command = [
                "python",
                str(self.sadtalker_dir / "inference.py"),
                "--driven_audio", wav_path,
                "--source_image", image_path,
                "--result_dir", str(temp_dir_path),
                "--still",
                "--preprocess", "full",
                "--enhancer", "gfpgan",
                "--facerender", "facevid2vid",
                "--batch_size", "1",
                "--fps", str(fps),
            ]

            logger.info("--- Running SadTalker ---")
            logger.info(f"Command: {' '.join(sadtalker_command)}")

            if not dry_run:
                try:
                    subprocess.run(sadtalker_command, check=True, capture_output=True, text=True)
                    # SadTalker often creates a file with a name based on inputs, find it
                    generated_files = list(temp_dir_path.glob("*.mp4"))
                    if not generated_files:
                        logger.error("SadTalker did not produce an output video file.")
                        return None
                    # Rename the first found mp4 to our expected name
                    shutil.move(generated_files[0], sadtalker_output_video)

                except subprocess.CalledProcessError as e:
                    logger.error(f"SadTalker execution failed with exit code {e.returncode}")
                    logger.error(f"Stdout: {e.stdout}")
                    logger.error(f"Stderr: {e.stderr}")
                    return None
            else:
                # In dry-run, we need a placeholder file for the next steps
                sadtalker_output_video.touch()


            # --- 2. Upscale with Real-ESRGAN ---
            upscaled_video = temp_dir_path / "upscaled.mp4"
            realesrgan_command = [
                "python",
                str(self.realesrgan_dir / "inference_realesrgan_video.py"),
                "-i", str(sadtalker_output_video),
                "-o", str(temp_dir_path),
                "-n", "RealESRGAN_x4plus",
                "--suffix", "upscaled",
                "--outscale", "4" # Will be downscaled later if > 1080p
            ]

            logger.info("--- Running Real-ESRGAN ---")
            logger.info(f"Command: {' '.join(realesrgan_command)}")

            if not dry_run:
                try:
                    subprocess.run(realesrgan_command, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Real-ESRGAN execution failed with exit code {e.returncode}")
                    logger.error(f"Stdout: {e.stdout}")
                    logger.error(f"Stderr: {e.stderr}")
                    return None
            else:
                upscaled_video.touch()


            # --- 3. Mux audio and finalize with ffmpeg ---
            final_output_dir = BASE_DIR / "artifacts" / "avatar"
            final_output_dir.mkdir(parents=True, exist_ok=True)
            final_output_path = final_output_dir / f"{Path(image_path).stem}_{Path(wav_path).stem}_final.mp4"

            # Use the upscaled video name Real-ESRGAN creates
            actual_upscaled_video = temp_dir_path / "sadtalker_output_upscaled.mp4"

            ffmpeg_command = [
                FFMPEG_PATH,
                "-y",
                "-i", str(actual_upscaled_video),
                "-i", wav_path,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-strict", "experimental",
                "-b:a", "192k",
                "-shortest",
                "-vf", "scale=-1:1080", # Scale height to 1080p, keep aspect ratio
                str(final_output_path)
            ]

            logger.info("--- Running ffmpeg ---")
            logger.info(f"Command: {' '.join(ffmpeg_command)}")

            if not dry_run:
                try:
                    subprocess.run(ffmpeg_command, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    logger.error(f"ffmpeg execution failed with exit code {e.returncode}")
                    logger.error(f"Stdout: {e.stdout}")
                    logger.error(f"Stderr: {e.stderr}")
                    return None

            logger.info(f"Successfully created final video: {final_output_path}")
            return str(final_output_path) if not dry_run else "dry_run_success"
