import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import core.env
from core.errors import ConfigError, ExternalToolError
from core.logging import logger
from services.sd_service import SDService  # Reuse the queuing and polling logic

# Base directory for artifacts
BASE_ARTIFACTS_DIR = Path("artifacts")

class AnimService(SDService):
    def __init__(self, comfyui_url: Optional[str] = None):
        super().__init__(comfyui_url)
        self.artifacts_dir = BASE_ARTIFACTS_DIR / "anim"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg_path = core.env.PATH_FFMPEG
        logger.info(f"AnimService initialized. FFMPEG path: {self.ffmpeg_path}")

    def plan_animation(
        self,
        prompt: str,
        seconds: int = 4,
        fps: int = 12,
        width: int = 512,
        height: int = 512,
        steps: int = 20
    ) -> Dict[str, Any]:
        """Computes frame count and validates bounds, returning a plan dictionary."""
        if not (1 <= seconds <= 10):
            raise ValueError("Seconds must be between 1 and 10.")
        if not (8 <= fps <= 24):
            raise ValueError("FPS must be between 8 and 24.")

        frame_count = seconds * fps
        plan = {
            "prompt": prompt,
            "seconds": seconds,
            "fps": fps,
            "width": width,
            "height": height,
            "steps": steps,
            "frame_count": frame_count,
        }
        logger.info(f"Animation planned: {frame_count} frames for '{prompt}'")
        return plan

    def render_animation(self, plan: Dict[str, Any]) -> str:
        """
        Renders an animation based on a plan by triggering AnimateDiff in ComfyUI,
        downloading the resulting frames, and muxing them into an MP4 with ffmpeg.
        """
        # For AnimateDiff, a specific workflow is required.
        # We assume a 'workflows/comfy/animatediff.json' exists.
        workflow_path = self.workflows_dir / "animatediff.json"
        if not workflow_path.exists():
            raise ConfigError(f"Workflow not found: {workflow_path}. Cannot render animation.")

        with open(workflow_path, "r") as f:
            prompt_workflow = json.load(f)

        # --- Inject plan parameters into the workflow ---
        # Note: Node IDs are specific to the assumed 'animatediff.json' workflow.
        # This part is highly dependent on the workflow's structure.
        # Example node injections:
        # prompt_workflow["positive_prompt_node_id"]["inputs"]["text"] = plan["prompt"]
        # prompt_workflow["sampler_node_id"]["inputs"]["steps"] = plan["steps"]
        # prompt_workflow["animatediff_loader_id"]["inputs"]["frame_count"] = plan["frame_count"]
        # ... and so on for width, height, etc.
        # For this implementation, we will assume a simple prompt injection.
        prompt_workflow["6"]["inputs"]["text"] = plan["prompt"] # Assuming node 6 is the positive prompt

        prompt_id = self._queue_prompt(prompt_workflow)
        logger.info(f"Queued AnimateDiff prompt with ID: {prompt_id}")

        # --- Create a job directory for the frames ---
        job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{prompt_id}"
        frames_dir = self.artifacts_dir / job_id / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        # --- Poll for completion and download frames ---
        timeout = 300  # Longer timeout for animations
        start_time = time.time()
        while time.time() - start_time < timeout:
            history = self._get_history(prompt_id)
            if prompt_id in history and 'outputs' in history[prompt_id]:
                outputs = history[prompt_id]['outputs']
                # In AnimateDiff, the output node (often a 'VideoCombine' or similar)
                # might give a list of frames. We'll look for 'images'.
                for node_id in outputs:
                    if 'images' in outputs[node_id]:
                        image_list = outputs[node_id]['images']
                        for i, image_data in enumerate(image_list):
                            image_bytes = self._get_image(
                                image_data['filename'],
                                image_data['subfolder'],
                                image_data['type']
                            )
                            frame_path = frames_dir / f"{i:06d}.png"
                            with open(frame_path, "wb") as f_out:
                                f_out.write(image_bytes)

                        logger.info(f"Downloaded {len(image_list)} frames to {frames_dir}")
                        return self._mux_frames_to_mp4(frames_dir.parent, plan['fps'])
            time.sleep(2)

        raise ExternalToolError("AnimateDiff task timed out waiting for ComfyUI.")

    def _mux_frames_to_mp4(self, job_dir: Path, fps: int) -> str:
        """Uses ffmpeg to combine frames into an MP4 video."""
        frames_pattern = job_dir / "frames" / "%06d.png"
        output_path = job_dir / "out.mp4"

        command = [
            self.ffmpeg_path,
            "-y",
            "-framerate", str(fps),
            "-i", str(frames_pattern),
            "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            str(output_path)
        ]

        logger.info(f"Running ffmpeg command: {' '.join(command)}")
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            logger.info(f"ffmpeg stdout: {result.stdout}")
            logger.info(f"Successfully created video: {output_path.resolve()}")
            return str(output_path.resolve())
        except FileNotFoundError:
            raise ExternalToolError(f"ffmpeg not found at '{self.ffmpeg_path}'. Please install it and ensure it's in your PATH or set PATH_FFMPEG.")
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed with exit code {e.returncode}")
            logger.error(f"ffmpeg stderr: {e.stderr}")
            raise ExternalToolError(f"ffmpeg failed to mux frames: {e.stderr}")

    async def animate_from_prompt(self, prompt: str) -> Path:
        """
        Vereinfachte Methode, die einen Prompt nimmt, daraus ein Bild generiert
        und dieses dann animiert.
        """
        # 1. Bild generieren (Abhängigkeit von SDService)
        # In einer echten Architektur wäre dies entkoppelt, z.B. über eine Queue.
        from services.sd_service import SDService
        sd_service = SDService()
        image_path = await sd_service.generate_image(prompt)

        # 2. Bild animieren (Annahme: animate_image nimmt einen Bildpfad)
        # Dies ist eine Platzhalterlogik, da die genaue Funktionsweise
        # von SadTalker/etc. von einem Input-Video und Audio abhängt.
        # Wir simulieren es hier mit dem generierten Bild.
        animated_path = self.animate_image(
            source_image=image_path,
            driving_video=self.driving_video, # Annahme: ein Standard-Video existiert
            preprocess="full",
            still=True
        )
        return animated_path