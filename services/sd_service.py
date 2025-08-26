import json
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import core.env
from core.errors import ConfigError, ExternalToolError
from core.logging import logger

# Base directory for artifacts
BASE_ARTIFACTS_DIR = Path("artifacts")

class SDService:
    def __init__(self, comfyui_url: Optional[str] = None):
        self.server_address = comfyui_url or core.env.COMFYUI_URL
        self.client_id = str(uuid.uuid4())
        self.artifacts_dir = BASE_ARTIFACTS_DIR / "images"
        self.workflows_dir = Path("workflows/comfy")

        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"SDService initialized. API: http://{self.server_address}, "
            f"Artifacts: {self.artifacts_dir}"
        )

# --- Singleton Pattern ---
_sd_service_instance: Optional[SDService] = None

def get_sd_service() -> SDService:
    """Returns the singleton instance of the SDService."""
    global _sd_service_instance
    if _sd_service_instance is None:
        _sd_service_instance = SDService()
    return _sd_service_instance

    def _queue_prompt(self, prompt_workflow: dict) -> str:
        """Sends a prompt to the ComfyUI queue and returns the prompt ID."""
        p = {"prompt": prompt_workflow, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(f"http://{self.server_address}/prompt", data=data)
        try:
            response = urllib.request.urlopen(req)
            result = json.loads(response.read())
            return result['prompt_id']
        except urllib.error.URLError as e:
            raise ExternalToolError(f"Failed to queue prompt in ComfyUI: {e.reason}")

    def _get_history(self, prompt_id: str) -> dict:
        """Gets the history for a given prompt ID."""
        try:
            with urllib.request.urlopen(f"http://{self.server_address}/history/{prompt_id}") as response:
                return json.loads(response.read())
        except urllib.error.URLError as e:
            raise ExternalToolError(f"Failed to get history from ComfyUI: {e.reason}")

    def _get_image(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        """Fetches an image from the ComfyUI server."""
        params = urllib.parse.urlencode({
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type
        })
        try:
            url = f"http://{self.server_address}/view?{params}"
            with urllib.request.urlopen(url) as response:
                return response.read()
        except urllib.error.URLError as e:
            raise ExternalToolError(
                f"Failed to download image from ComfyUI: {e.reason}"
            )

    def txt2img(
        self,
        prompt: str,
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        seed: Optional[int] = None,
        negative_prompt: Optional[str] = None
    ) -> bytes:
        """
        Generates an image from a text prompt and returns the image as bytes.
        """
        workflow_path = self.workflows_dir / "sd15_txt2img.json"
        if not workflow_path.exists():
            raise ConfigError(
                f"Workflow not found: {workflow_path}. Cannot perform txt2img."
            )

        with open(workflow_path, "r") as f:
            prompt_workflow = json.load(f)

        # Modify the workflow with the provided parameters
        # These node IDs are specific to the sd15_txt2img.json workflow
        prompt_workflow["6"]["inputs"]["text"] = prompt
        prompt_workflow["7"]["inputs"]["text"] = negative_prompt or ""
        prompt_workflow["3"]["inputs"]["seed"] = (
            seed if seed is not None else int(time.time())
        )
        prompt_workflow["5"]["inputs"]["width"] = width
        prompt_workflow["5"]["inputs"]["height"] = height
        prompt_workflow["3"]["inputs"]["steps"] = steps

        prompt_id = self._queue_prompt(prompt_workflow)
        logger.info(f"Queued txt2img prompt with ID: {prompt_id}")

        # Poll for completion
        timeout = 120
        start_time = time.time()
        while time.time() - start_time < timeout:
            history = self._get_history(prompt_id)
            if prompt_id in history and 'outputs' in history[prompt_id]:
                outputs = history[prompt_id]['outputs']
                # Find the final image output node (usually 'SaveImage')
                for node_id in outputs:
                    if 'images' in outputs[node_id]:
                        image_data = outputs[node_id]['images'][0]
                        image_bytes = self._get_image(
                            image_data['filename'],
                            image_data['subfolder'],
                            image_data['type']
                        )
                        logger.info(f"Successfully generated image bytes for prompt ID: {prompt_id}")
                        return image_bytes
            time.sleep(1)

        raise ExternalToolError("txt2img task timed out waiting for ComfyUI.")

    def upscale(self, image_path: str, model: Optional[str] = None) -> str:
        """Upscales an image using a pre-defined ComfyUI workflow."""
        # This implementation would be very similar to txt2img:
        # 1. Load workflows/comfy/upscale.json
        # 2. Add a 'LoadImage' node to the workflow graph pointing to image_path.
        # 3. Connect the 'LoadImage' node to the upscaling model node.
        # 4. Queue, poll, download, and save.
        # For now, we will raise NotImplementedError.
        raise NotImplementedError("Upscale functionality is not yet fully implemented.")
