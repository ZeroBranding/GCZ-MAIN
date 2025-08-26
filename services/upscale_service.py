#!/usr/bin/env python3
"""Upscale Service - Image upscaling using ComfyUI."""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import yaml

from core.errors import ConfigError, ExternalToolError
from core.logging import logger


class ComfyClient:
    """Shared ComfyUI client for interacting with the ComfyUI API."""
    
    def __init__(self, server_address: Optional[str] = None):
        """Initialize ComfyUI client."""
        self.server_address = server_address or os.getenv("COMFYUI_URL", "127.0.0.1:8188")
        self.client_id = str(uuid.uuid4())
        
    def _post(self, workflow_json: Dict[str, Any], inputs: Dict[str, Any]) -> str:
        """
        Post a workflow to ComfyUI with inputs.
        
        Args:
            workflow_json: The workflow definition
            inputs: Input parameters to inject into the workflow
            
        Returns:
            prompt_id for tracking the job
        """
        # Clone the workflow to avoid modifying the original
        workflow = json.loads(json.dumps(workflow_json))
        
        # Apply inputs to the workflow
        for node_id, node_inputs in inputs.items():
            if node_id in workflow:
                if "inputs" not in workflow[node_id]:
                    workflow[node_id]["inputs"] = {}
                workflow[node_id]["inputs"].update(node_inputs)
        
        # Prepare the request
        payload = {
            "prompt": workflow,
            "client_id": self.client_id
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            f"http://{self.server_address}/prompt",
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read())
                return result.get('prompt_id')
        except urllib.error.URLError as e:
            raise ExternalToolError(f"Failed to queue prompt in ComfyUI: {e}")
            
    def _poll(self, job_id: str, timeout: int = 120) -> Dict[str, Any]:
        """
        Poll ComfyUI for job completion.
        
        Args:
            job_id: The prompt_id to poll
            timeout: Maximum time to wait in seconds
            
        Returns:
            The job outputs when complete
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                url = f"http://{self.server_address}/history/{job_id}"
                with urllib.request.urlopen(url) as response:
                    history = json.loads(response.read())
                    
                if job_id in history:
                    job_data = history[job_id]
                    if 'outputs' in job_data:
                        return job_data['outputs']
                        
            except urllib.error.URLError as e:
                logger.warning(f"Failed to get history: {e}")
                
            time.sleep(1)
            
        raise ExternalToolError(f"Job {job_id} timed out after {timeout} seconds")
        
    def get_image(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        """Download an image from ComfyUI server."""
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
            raise ExternalToolError(f"Failed to download image from ComfyUI: {e}")
            
    def upload_image(self, image_path: str) -> Tuple[str, str]:
        """
        Upload an image to ComfyUI server.
        
        Returns:
            Tuple of (filename, subfolder) for referencing the uploaded image
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
            
        # Read and encode the image
        with open(image_path, 'rb') as f:
            image_data = f.read()
            
        # Create multipart form data
        boundary = f'----WebKitFormBoundary{uuid.uuid4().hex}'
        body = []
        
        # Add image field
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"')
        body.append('Content-Type: image/png')
        body.append('')
        body.append('')  # Empty line before binary data
        
        # Join text parts and add binary data
        body_text = '\r\n'.join(body).encode('utf-8')
        body_binary = body_text + image_data + f'\r\n--{boundary}--\r\n'.encode('utf-8')
        
        # Send request
        req = urllib.request.Request(
            f"http://{self.server_address}/upload/image",
            data=body_binary,
            headers={
                'Content-Type': f'multipart/form-data; boundary={boundary}'
            }
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read())
                return result.get('name', image_path.name), result.get('subfolder', '')
        except urllib.error.URLError as e:
            # Fallback: reference the image by its path
            logger.warning(f"Failed to upload image, using local path: {e}")
            return str(image_path), ''


class UpscaleService:
    """Service for upscaling images using ComfyUI."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the upscale service."""
        self.client = ComfyClient()
        self.artifacts_dir = Path("artifacts") / "upscaled"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        self.config = self._load_config(config_path)
        self.default_scale = self.config.get('presets', {}).get('default_scale', 4)
        self.unsharp = self.config.get('presets', {}).get('unsharp', False)
        
        logger.info(f"UpscaleService initialized with server: {self.client.server_address}")
        
    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if config_path is None:
            config_path = "configs/upscale.yml"
            
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r') as f:
                return yaml.safe_load(f) or {}
        return {}
        
    def _create_upscale_workflow(self, scale: int = 4) -> Dict[str, Any]:
        """Create a ComfyUI workflow for upscaling."""
        # Create a proper ComfyUI workflow structure
        workflow = {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": "input.png",
                    "upload": "image"
                }
            },
            "2": {
                "class_type": "ImageUpscaleWithModel",
                "inputs": {
                    "upscale_model": f"RealESRGAN_x{scale}.pth",
                    "image": ["1", 0]  # Link to LoadImage output
                }
            },
            "3": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["2", 0],  # Link to upscaler output
                    "filename_prefix": "upscaled"
                }
            }
        }
        
        return workflow
        
    def upscale(
        self,
        image_path: str,
        scale: Optional[int] = None,
        output_path: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upscale an image using ComfyUI.
        
        Args:
            image_path: Path to input image
            scale: Upscale factor (2 or 4)
            output_path: Optional output path
            model: Optional model name
            
        Returns:
            Dict with output_path and metadata
        """
        start_time = time.time()
        
        # Validate inputs
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Input image not found: {image_path}")
            
        scale = scale or self.default_scale
        if scale not in [2, 4]:
            raise ValueError(f"Invalid scale: {scale}. Must be 2 or 4.")
            
        logger.info(f"Starting upscale: {image_path} @ {scale}x")
        
        try:
            # Upload the image to ComfyUI
            filename, subfolder = self.client.upload_image(str(image_path))
            
            # Create workflow
            workflow = self._create_upscale_workflow(scale)
            
            # Update workflow with uploaded image reference
            workflow["1"]["inputs"]["image"] = filename
            if subfolder:
                workflow["1"]["inputs"]["subfolder"] = subfolder
                
            # If custom model specified, update it
            if model:
                workflow["2"]["inputs"]["upscale_model"] = model
                
            # Submit workflow
            job_id = self.client._post(workflow, {})
            logger.info(f"Submitted upscale job: {job_id}")
            
            # Poll for completion
            outputs = self.client._poll(job_id, timeout=120)
            
            # Find the output image
            for node_id, node_output in outputs.items():
                if 'images' in node_output and len(node_output['images']) > 0:
                    image_info = node_output['images'][0]
                    
                    # Download the result
                    image_bytes = self.client.get_image(
                        image_info['filename'],
                        image_info.get('subfolder', ''),
                        image_info.get('type', 'output')
                    )
                    
                    # Save to output path
                    if output_path:
                        final_path = Path(output_path)
                    else:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        final_path = self.artifacts_dir / f"{image_path.stem}_x{scale}_{timestamp}.png"
                        
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(final_path, 'wb') as f:
                        f.write(image_bytes)
                        
                    duration = time.time() - start_time
                    
                    logger.info(f"Upscale complete in {duration:.2f}s: {final_path}")
                    
                    return {
                        'output_path': str(final_path.resolve()),
                        'scale': scale,
                        'duration': duration,
                        'input_path': str(image_path.resolve()),
                        'model': model or f"RealESRGAN_x{scale}"
                    }
                    
            raise ExternalToolError("No output image found in ComfyUI response")
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Upscale failed after {duration:.2f}s: {e}")
            raise


def main():
    """CLI entry point for upscale service."""
    parser = argparse.ArgumentParser(description='Upscale images using ComfyUI')
    parser.add_argument('--in', dest='input_path', required=True,
                        help='Input image path')
    parser.add_argument('--scale', type=int, choices=[2, 4], default=4,
                        help='Upscale factor (2 or 4)')
    parser.add_argument('--out', dest='output_path',
                        help='Output image path (optional)')
    parser.add_argument('--model', help='Model name (optional)')
    parser.add_argument('--config', help='Config file path')
    parser.add_argument('--server', help='ComfyUI server address')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set up logging
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    # Override server if specified
    if args.server:
        os.environ['COMFYUI_URL'] = args.server
    
    try:
        # Initialize service
        service = UpscaleService(config_path=args.config)
        
        # Perform upscale
        result = service.upscale(
            image_path=args.input_path,
            scale=args.scale,
            output_path=args.output_path,
            model=args.model
        )
        
        # Print result
        print(f"✓ Upscaled image saved to: {result['output_path']}")
        print(f"  Scale: {result['scale']}x")
        print(f"  Duration: {result['duration']:.2f}s")
        print(f"  Model: {result['model']}")
        
        return 0
        
    except FileNotFoundError as e:
        print(f"✗ File not found: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"✗ Invalid argument: {e}", file=sys.stderr)
        return 1
    except ExternalToolError as e:
        print(f"✗ ComfyUI error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"✗ Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 3


if __name__ == '__main__':
    sys.exit(main())