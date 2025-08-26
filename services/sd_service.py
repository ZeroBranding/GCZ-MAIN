import json
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import core.env
from core.errors import ConfigError, ExternalToolError
from core.logging import logger

# Import shared ComfyClient
try:
    from services.upscale_service import ComfyClient
except ImportError:
    # Fallback if upscale_service is not available
    ComfyClient = None

# Base directory for artifacts
BASE_ARTIFACTS_DIR = Path("artifacts")


class SDService:
    def __init__(self, comfyui_url: Optional[str] = None):
        if ComfyClient:
            self.client = ComfyClient(comfyui_url)
            self.server_address = self.client.server_address
        else:
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
        if ComfyClient and hasattr(self, 'client'):
            return self.client._post(prompt_workflow, {})
        else:
            # Fallback to original implementation
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
        if ComfyClient and hasattr(self, 'client'):
            return self.client.get_image(filename, subfolder, folder_type)
        else:
            # Fallback to original implementation
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
                
    def _poll_for_completion(self, prompt_id: str, timeout: int = 120) -> Dict[str, Any]:
        """Poll for workflow completion and return outputs."""
        if ComfyClient and hasattr(self, 'client'):
            return self.client._poll(prompt_id, timeout)
        else:
            # Original polling logic
            start_time = time.time()
            while time.time() - start_time < timeout:
                history = self._get_history(prompt_id)
                if prompt_id in history and 'outputs' in history[prompt_id]:
                    return history[prompt_id]['outputs']
                time.sleep(1)
            raise ExternalToolError(f"Task timed out waiting for ComfyUI after {timeout}s")

    def txt2img(
        self,
        prompt: str,
        seed: Optional[int] = None,
<<<<<<< HEAD
        negative_prompt: Optional[str] = None
    ) -> bytes:
        """
        Generates an image from a text prompt and returns the image as bytes.
=======
        steps: Optional[int] = None,
        cfg: Optional[float] = None,
        size: Optional[tuple] = None,
        negative_prompt: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generates an image from a text prompt via a pre-defined workflow.
        
        Args:
            prompt: Text prompt for generation
            seed: Random seed for reproducibility
            steps: Number of inference steps (default: 20)
            cfg: CFG scale (default: 7.0)
            size: Tuple of (width, height) or use width/height directly
            negative_prompt: Negative prompt
            width: Image width (default: 512)
            height: Image height (default: 512)
            
        Returns:
            Dict with path and metadata
>>>>>>> origin/cursor/implementiere-langgraph-runtime-als-br-cke-zur-engine-8742
        """
        workflow_path = self.workflows_dir / "sd15_txt2img.json"
        if not workflow_path.exists():
            raise ConfigError(
                f"Workflow not found: {workflow_path}. Cannot perform txt2img."
            )

        with open(workflow_path, "r") as f:
            prompt_workflow = json.load(f)

        # Handle size parameter
        if size:
            width, height = size
        else:
            width = width or 512
            height = height or 512
            
        steps = steps or 20
        cfg = cfg or 7.0
        seed = seed if seed is not None else int(time.time())

        # Modify the workflow with the provided parameters
        # These node IDs are specific to the sd15_txt2img.json workflow
        prompt_workflow["6"]["inputs"]["text"] = prompt
        prompt_workflow["7"]["inputs"]["text"] = negative_prompt or ""
        prompt_workflow["3"]["inputs"]["seed"] = seed
        prompt_workflow["5"]["inputs"]["width"] = width
        prompt_workflow["5"]["inputs"]["height"] = height
        prompt_workflow["3"]["inputs"]["steps"] = steps
        if "cfg" in prompt_workflow["3"]["inputs"]:
            prompt_workflow["3"]["inputs"]["cfg"] = cfg

        prompt_id = self._queue_prompt(prompt_workflow)
        logger.info(f"Queued txt2img prompt with ID: {prompt_id}")

        # Poll for completion
<<<<<<< HEAD
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
=======
        outputs = self._poll_for_completion(prompt_id, timeout=120)
        
        # Find the final image output node (usually 'SaveImage')
        for node_id in outputs:
            if 'images' in outputs[node_id]:
                image_data = outputs[node_id]['images'][0]
                image_bytes = self._get_image(
                    image_data['filename'],
                    image_data['subfolder'],
                    image_data['type']
                )

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"IMG_{timestamp}_{seed}.png"
                output_path = self.artifacts_dir / output_filename

                with open(output_path, "wb") as f_out:
                    f_out.write(image_bytes)

                logger.info(f"Image saved to: {output_path.resolve()}")
                
                return {
                    "path": str(output_path.resolve()),
                    "meta": {
                        "prompt": prompt,
                        "negative_prompt": negative_prompt,
                        "seed": seed,
                        "steps": steps,
                        "cfg": cfg,
                        "width": width,
                        "height": height,
                        "timestamp": timestamp
                    }
                }
>>>>>>> origin/cursor/implementiere-langgraph-runtime-als-br-cke-zur-engine-8742

        raise ExternalToolError("txt2img task completed but no image output found.")
        
    def img2img(
        self,
        image_path: str,
        prompt: Optional[str] = None,
        strength: Optional[float] = None,
        seed: Optional[int] = None,
        steps: Optional[int] = None,
        cfg: Optional[float] = None,
        negative_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates an image from an input image and optional prompt.
        
        Args:
            image_path: Path to input image
            prompt: Optional text prompt for guidance
            strength: Denoising strength (0.0-1.0, default: 0.75)
            seed: Random seed
            steps: Number of inference steps
            cfg: CFG scale
            negative_prompt: Negative prompt
            
        Returns:
            Dict with path and metadata
        """
        # Check if workflow exists
        workflow_path = self.workflows_dir / "sd15_img2img.json"
        if not workflow_path.exists():
            # Create a basic img2img workflow if it doesn't exist
            workflow = self._create_img2img_workflow()
        else:
            with open(workflow_path, "r") as f:
                workflow = json.load(f)
                
        # Set default values
        prompt = prompt or "enhance image, high quality"
        strength = strength or 0.75
        steps = steps or 20
        cfg = cfg or 7.0
        seed = seed if seed is not None else int(time.time())
        
        # Upload image if using ComfyClient
        if ComfyClient and hasattr(self, 'client'):
            filename, subfolder = self.client.upload_image(image_path)
            # Update workflow with uploaded image
            if "1" in workflow:  # Assuming node 1 is LoadImage
                workflow["1"]["inputs"]["image"] = filename
                if subfolder:
                    workflow["1"]["inputs"]["subfolder"] = subfolder
        else:
            # For basic implementation, just reference the path
            if "1" in workflow:
                workflow["1"]["inputs"]["image"] = image_path
                
        # Update workflow parameters
        # Node IDs may vary based on workflow structure
        if "6" in workflow:  # Positive prompt
            workflow["6"]["inputs"]["text"] = prompt
        if "7" in workflow:  # Negative prompt
            workflow["7"]["inputs"]["text"] = negative_prompt or ""
        if "3" in workflow:  # KSampler
            workflow["3"]["inputs"]["seed"] = seed
            workflow["3"]["inputs"]["steps"] = steps
            workflow["3"]["inputs"]["cfg"] = cfg
            workflow["3"]["inputs"]["denoise"] = strength
            
        # Queue and process
        prompt_id = self._queue_prompt(workflow)
        logger.info(f"Queued img2img prompt with ID: {prompt_id}")
        
        # Poll for completion
        outputs = self._poll_for_completion(prompt_id, timeout=120)
        
        # Find output image
        for node_id in outputs:
            if 'images' in outputs[node_id]:
                image_data = outputs[node_id]['images'][0]
                image_bytes = self._get_image(
                    image_data['filename'],
                    image_data['subfolder'],
                    image_data['type']
                )
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"IMG_i2i_{timestamp}_{seed}.png"
                output_path = self.artifacts_dir / output_filename
                
                with open(output_path, "wb") as f_out:
                    f_out.write(image_bytes)
                    
                logger.info(f"img2img result saved to: {output_path.resolve()}")
                
                return {
                    "path": str(output_path.resolve()),
                    "meta": {
                        "input_image": image_path,
                        "prompt": prompt,
                        "negative_prompt": negative_prompt,
                        "strength": strength,
                        "seed": seed,
                        "steps": steps,
                        "cfg": cfg,
                        "timestamp": timestamp
                    }
                }
                
        raise ExternalToolError("img2img task completed but no image output found.")
        
    def _create_img2img_workflow(self) -> Dict[str, Any]:
        """Create a basic img2img workflow structure."""
        return {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": "input.png",
                    "upload": "image"
                }
            },
            "2": {
                "class_type": "VAEEncode",
                "inputs": {
                    "pixels": ["1", 0],
                    "vae": ["4", 0]
                }
            },
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 0,
                    "steps": 20,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 0.75,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["2", 0]
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "sd15.safetensors"
                }
            },
            "5": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "enhance image",
                    "clip": ["4", 1]
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "",
                    "clip": ["4", 1]
                }
            },
            "8": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["5", 0],
                    "filename_prefix": "img2img"
                }
            }
        }

    def upscale(self, image_path: str, model: Optional[str] = None, scale: int = 4) -> Dict[str, Any]:
        """
        Upscales an image using ComfyUI upscale service.
        
        Args:
            image_path: Path to input image
            model: Optional model name
            scale: Upscale factor (2 or 4)
            
        Returns:
            Dict with path and metadata
        """
        # Use the UpscaleService if available
        try:
            from services.upscale_service import UpscaleService
            service = UpscaleService()
            result = service.upscale(image_path, scale=scale, model=model)
            return {
                "path": result["output_path"],
                "meta": {
                    "input_path": result["input_path"],
                    "scale": result["scale"],
                    "model": result["model"],
                    "duration": result["duration"]
                }
            }
        except ImportError:
            raise NotImplementedError("Upscale functionality requires upscale_service module.")
