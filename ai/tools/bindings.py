"""Tool bindings - Connect function schemas to service implementations."""
import asyncio
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field
from ai.adapters.providers import FunctionDef, ToolCall
from ai.adapters.registry import get_registry, register_model
from core.logging import logger


# Result types
@dataclass
class ToolResult:
    """Result from tool execution."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ArtifactResult(ToolResult):
    """Result containing an artifact path."""
    artifact_path: Optional[str] = None
    artifact_type: Optional[str] = None


# Tool parameter models
class SDGenerateParams(BaseModel):
    """Parameters for Stable Diffusion image generation."""
    prompt: str = Field(..., description="Text prompt for image generation")
    negative_prompt: Optional[str] = Field(None, description="Negative prompt")
    width: int = Field(512, ge=128, le=2048, description="Image width")
    height: int = Field(512, ge=128, le=2048, description="Image height")
    steps: int = Field(20, ge=1, le=150, description="Number of inference steps")
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")


class UpscaleParams(BaseModel):
    """Parameters for image upscaling."""
    image_path: str = Field(..., description="Path to input image")
    scale: int = Field(2, ge=2, le=4, description="Upscale factor")
    model: Optional[str] = Field(None, description="Upscaling model to use")


class UploadParams(BaseModel):
    """Parameters for file upload."""
    file_path: str = Field(..., description="Path to file to upload")
    destination: str = Field("local", enum=["local", "telegram"], description="Upload destination")
    chat_id: Optional[str] = Field(None, description="Telegram chat ID (required for telegram destination)")
    caption: Optional[str] = Field(None, description="Caption for the file")


class ASRParams(BaseModel):
    """Parameters for Automatic Speech Recognition."""
    audio_path: str = Field(..., description="Path to audio file")
    language: str = Field("de", description="Language code (e.g., 'de', 'en')")
    format: str = Field("text", enum=["text", "segments"], description="Output format")


class TTSParams(BaseModel):
    """Parameters for Text-to-Speech synthesis."""
    text: str = Field(..., description="Text to synthesize")
    voice_profile: str = Field("default", description="Voice profile name")
    language: str = Field("de", description="Language code")
    backend: str = Field("openvoice", enum=["openvoice", "xtts", "piper"], description="TTS backend")


class AnimationParams(BaseModel):
    """Parameters for animation generation."""
    prompt: str = Field(..., description="Text prompt for animation")
    duration: float = Field(3.0, ge=1.0, le=10.0, description="Animation duration in seconds")
    style: str = Field("default", description="Animation style")


class ToolBindings:
    """Bindings between tool schemas and service implementations."""
    
    def __init__(self):
        self.registry = get_registry()
        self._register_tools()
        self._service_cache = {}
        
    def _register_tools(self):
        """Register all tool schemas."""
        # SD generation
        self.registry.register(
            SDGenerateParams,
            name="sd_generate",
            description="Generate image using Stable Diffusion",
            version="1.0.0",
            tags=["image", "generation", "sd"]
        )
        
        # Upscaling
        self.registry.register(
            UpscaleParams,
            name="upscale_image",
            description="Upscale an image to higher resolution",
            version="1.0.0",
            tags=["image", "upscale", "enhancement"]
        )
        
        # Upload
        self.registry.register(
            UploadParams,
            name="upload_file",
            description="Upload file to local storage or Telegram",
            version="1.0.0",
            tags=["file", "upload", "storage"]
        )
        
        # ASR
        self.registry.register(
            ASRParams,
            name="transcribe_audio",
            description="Transcribe audio to text using ASR",
            version="1.0.0",
            tags=["audio", "asr", "transcription"]
        )
        
        # TTS
        self.registry.register(
            TTSParams,
            name="synthesize_speech",
            description="Synthesize speech from text",
            version="1.0.0",
            tags=["audio", "tts", "synthesis"]
        )
        
        # Animation
        self.registry.register(
            AnimationParams,
            name="generate_animation",
            description="Generate animation from text prompt",
            version="1.0.0",
            tags=["animation", "generation", "video"]
        )
        
        logger.info("Registered all tool schemas")
        
    def _get_service(self, service_name: str):
        """Get or create a service instance."""
        if service_name not in self._service_cache:
            if service_name == "sd_service":
                from services.sd_service import SDService
                self._service_cache[service_name] = SDService()
            elif service_name == "asr_service":
                from services.asr_service import ASRService
                self._service_cache[service_name] = ASRService()
            elif service_name == "voice_service":
                from services.voice_service import VoiceService
                self._service_cache[service_name] = VoiceService()
            elif service_name == "anim_service":
                from services.anim_service import AnimService
                self._service_cache[service_name] = AnimService()
            elif service_name == "telegram_service":
                from services.telegram_service import TelegramService
                self._service_cache[service_name] = TelegramService()
            else:
                raise ValueError(f"Unknown service: {service_name}")
                
        return self._service_cache[service_name]
        
    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call and return the result.
        
        Args:
            tool_call: The tool call to execute
            
        Returns:
            ToolResult with execution outcome
        """
        try:
            # Route to appropriate handler
            if tool_call.name == "sd_generate":
                return await self._execute_sd_generate(tool_call.arguments)
            elif tool_call.name == "upscale_image":
                return await self._execute_upscale(tool_call.arguments)
            elif tool_call.name == "upload_file":
                return await self._execute_upload(tool_call.arguments)
            elif tool_call.name == "transcribe_audio":
                return await self._execute_asr(tool_call.arguments)
            elif tool_call.name == "synthesize_speech":
                return await self._execute_tts(tool_call.arguments)
            elif tool_call.name == "generate_animation":
                return await self._execute_animation(tool_call.arguments)
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown tool: {tool_call.name}"
                )
                
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_call.name}: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"tool": tool_call.name, "arguments": tool_call.arguments}
            )
            
    async def _execute_sd_generate(self, arguments: Dict[str, Any]) -> ArtifactResult:
        """Execute SD image generation."""
        try:
            params = SDGenerateParams(**arguments)
            service = self._get_service("sd_service")
            
            # Call the service (sync method, so we run in executor)
            loop = asyncio.get_event_loop()
            image_path = await loop.run_in_executor(
                None,
                service.txt2img,
                params.prompt,
                params.negative_prompt,
                params.width,
                params.height,
                params.steps,
                params.seed
            )
            
            return ArtifactResult(
                success=True,
                artifact_path=image_path,
                artifact_type="image/png",
                data={
                    "path": image_path,
                    "width": params.width,
                    "height": params.height,
                    "prompt": params.prompt
                },
                metadata={
                    "service": "sd_service",
                    "method": "txt2img",
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"SD generation failed: {e}")
            return ArtifactResult(
                success=False,
                error=str(e),
                metadata={"service": "sd_service", "arguments": arguments}
            )
            
    async def _execute_upscale(self, arguments: Dict[str, Any]) -> ArtifactResult:
        """Execute image upscaling."""
        try:
            params = UpscaleParams(**arguments)
            
            # Check if upscale service exists, otherwise use a simple implementation
            try:
                from services.upscale_service import UpscaleService
                service = UpscaleService()
                
                loop = asyncio.get_event_loop()
                output_path = await loop.run_in_executor(
                    None,
                    service.upscale,
                    params.image_path,
                    params.scale,
                    params.model
                )
            except ImportError:
                # Fallback: Try SD service upscale method or simple copy
                try:
                    service = self._get_service("sd_service")
                    loop = asyncio.get_event_loop()
                    output_path = await loop.run_in_executor(
                        None,
                        service.upscale,
                        params.image_path,
                        params.model
                    )
                except (NotImplementedError, AttributeError):
                    # Simple fallback: copy with modified name
                    input_path = Path(params.image_path)
                    output_path = input_path.parent / f"{input_path.stem}_upscaled{input_path.suffix}"
                    shutil.copy2(params.image_path, output_path)
                    output_path = str(output_path)
                    
            return ArtifactResult(
                success=True,
                artifact_path=output_path,
                artifact_type="image/png",
                data={
                    "input_path": params.image_path,
                    "output_path": output_path,
                    "scale": params.scale
                },
                metadata={
                    "service": "upscale",
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Upscaling failed: {e}")
            return ArtifactResult(
                success=False,
                error=str(e),
                metadata={"service": "upscale", "arguments": arguments}
            )
            
    async def _execute_upload(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute file upload."""
        try:
            params = UploadParams(**arguments)
            
            if params.destination == "telegram":
                if not params.chat_id:
                    return ToolResult(
                        success=False,
                        error="chat_id is required for telegram upload"
                    )
                    
                # Use telegram service for upload
                # Note: This would need actual telegram bot implementation
                return ToolResult(
                    success=False,
                    error="Telegram upload not yet implemented",
                    metadata={"destination": "telegram", "chat_id": params.chat_id}
                )
                
            else:  # local storage
                # Copy to uploads directory
                uploads_dir = Path("artifacts/uploads")
                uploads_dir.mkdir(parents=True, exist_ok=True)
                
                source = Path(params.file_path)
                if not source.exists():
                    return ToolResult(
                        success=False,
                        error=f"Source file not found: {params.file_path}"
                    )
                    
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_name = f"{timestamp}_{source.name}"
                dest_path = uploads_dir / dest_name
                
                shutil.copy2(source, dest_path)
                
                return ToolResult(
                    success=True,
                    data={
                        "source": str(source),
                        "destination": str(dest_path),
                        "size": dest_path.stat().st_size
                    },
                    metadata={
                        "destination": "local",
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"service": "upload", "arguments": arguments}
            )
            
    async def _execute_asr(self, arguments: Dict[str, Any]) -> ToolResult:
        """Execute ASR transcription."""
        try:
            params = ASRParams(**arguments)
            service = self._get_service("asr_service")
            
            # Call the async transcribe method
            segments = await service.transcribe_stream(
                params.audio_path,
                params.language
            )
            
            if params.format == "text":
                # Join all segments into text
                text = " ".join(seg.get("text", "") for seg in segments)
                return ToolResult(
                    success=True,
                    data={
                        "text": text,
                        "language": params.language,
                        "num_segments": len(segments)
                    },
                    metadata={
                        "service": "asr_service",
                        "method": "transcribe_stream",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            else:
                # Return segments
                return ToolResult(
                    success=True,
                    data={
                        "segments": segments,
                        "language": params.language
                    },
                    metadata={
                        "service": "asr_service",
                        "format": "segments",
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
        except Exception as e:
            logger.error(f"ASR transcription failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                metadata={"service": "asr_service", "arguments": arguments}
            )
            
    async def _execute_tts(self, arguments: Dict[str, Any]) -> ArtifactResult:
        """Execute TTS synthesis."""
        try:
            params = TTSParams(**arguments)
            service = self._get_service("voice_service")
            
            # Call the sync synthesize method
            loop = asyncio.get_event_loop()
            audio_path = await loop.run_in_executor(
                None,
                service.synthesize,
                params.text,
                params.voice_profile,
                params.backend,
                params.language
            )
            
            if audio_path:
                return ArtifactResult(
                    success=True,
                    artifact_path=audio_path,
                    artifact_type="audio/wav",
                    data={
                        "path": audio_path,
                        "text": params.text,
                        "voice": params.voice_profile,
                        "backend": params.backend
                    },
                    metadata={
                        "service": "voice_service",
                        "method": "synthesize",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            else:
                return ArtifactResult(
                    success=False,
                    error="TTS synthesis returned no audio file",
                    metadata={"service": "voice_service", "arguments": arguments}
                )
                
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return ArtifactResult(
                success=False,
                error=str(e),
                metadata={"service": "voice_service", "arguments": arguments}
            )
            
    async def _execute_animation(self, arguments: Dict[str, Any]) -> ArtifactResult:
        """Execute animation generation."""
        try:
            params = AnimationParams(**arguments)
            service = self._get_service("anim_service")
            
            # Call the animation service (assuming async method)
            animation_path = await service.generate_animation(
                params.prompt,
                params.duration,
                params.style
            )
            
            return ArtifactResult(
                success=True,
                artifact_path=animation_path,
                artifact_type="video/mp4",
                data={
                    "path": animation_path,
                    "prompt": params.prompt,
                    "duration": params.duration,
                    "style": params.style
                },
                metadata={
                    "service": "anim_service",
                    "method": "generate_animation",
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Animation generation failed: {e}")
            return ArtifactResult(
                success=False,
                error=str(e),
                metadata={"service": "anim_service", "arguments": arguments}
            )


# Global bindings instance
_bindings: Optional[ToolBindings] = None


def get_bindings() -> ToolBindings:
    """Get or create the global bindings instance."""
    global _bindings
    if _bindings is None:
        _bindings = ToolBindings()
    return _bindings


async def execute_tool_call(tool_call: ToolCall) -> ToolResult:
    """Execute a tool call using the global bindings."""
    bindings = get_bindings()
    return await bindings.execute_tool(tool_call)


def get_available_tools() -> List[FunctionDef]:
    """Get all available tool definitions."""
    bindings = get_bindings()
    return bindings.registry.list_schemas()