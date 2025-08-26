"""
OpenAI Function Schemas für Kern-Tools
Definiert strikt typisierte Pydantic-Modelle für alle Tool-Parameter.
"""

from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal, Union
from pydantic import BaseModel, Field, validator, root_validator
import json


# === Core Types & Enums ===

class ImageModel(str, Enum):
    """Verfügbare Stable Diffusion Modelle."""
    SD15 = "sd15"
    SD21 = "sd21"
    SDXL = "sdxl"
    CUSTOM = "custom"


class UpscaleScale(int, Enum):
    """Erlaubte Upscale-Faktoren."""
    X2 = 2
    X4 = 4


class UploadTarget(str, Enum):
    """Upload-Ziele."""
    TELEGRAM = "telegram"
    DISK = "disk"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"


class VoiceModel(str, Enum):
    """Verfügbare TTS-Stimmen."""
    DE_SPEAKER = "de-speaker"
    EN_SPEAKER = "en-speaker"
    FEMALE = "female"
    MALE = "male"
    NEUTRAL = "neutral"


class LanguageCode(str, Enum):
    """Unterstützte Sprachen für ASR."""
    AUTO = "auto"
    DE = "de"
    EN = "en"
    FR = "fr"
    ES = "es"
    IT = "it"


# === Tool Parameter Models ===

class SDText2ImgParams(BaseModel):
    """Stable Diffusion Text-to-Image Parameter."""
    
    prompt: str = Field(
        ...,
        description="Text prompt for image generation",
        min_length=1,
        max_length=500,
        example="a beautiful landscape with mountains and lakes"
    )
    
    seed: Optional[int] = Field(
        None,
        description="Random seed for reproducible generation",
        ge=0,
        le=2147483647,  # Max int32
        example=42
    )
    
    steps: Optional[int] = Field(
        20,
        description="Number of inference steps",
        ge=10,
        le=50,
        example=20
    )
    
    cfg_scale: Optional[float] = Field(
        7.0,
        description="CFG scale for prompt adherence",
        ge=1.0,
        le=20.0,
        example=7.5,
        alias="cfg"
    )
    
    width: Optional[int] = Field(
        512,
        description="Image width in pixels",
        ge=256,
        le=1024,
        multiple_of=64,  # SD requirement
        example=512
    )
    
    height: Optional[int] = Field(
        512,
        description="Image height in pixels", 
        ge=256,
        le=1024,
        multiple_of=64,
        example=512
    )
    
    model: Optional[ImageModel] = Field(
        ImageModel.SD15,
        description="Stable Diffusion model to use",
        example="sd15"
    )
    
    negative_prompt: Optional[str] = Field(
        None,
        description="Negative prompt to avoid unwanted elements",
        max_length=200,
        example="blurry, low quality, distorted"
    )
    
    @validator('prompt')
    def validate_prompt(cls, v):
        """Validate prompt content."""
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        
        # Basic content filtering
        forbidden_words = ["nsfw", "nude", "explicit"]
        if any(word in v.lower() for word in forbidden_words):
            raise ValueError("Inappropriate content detected")
        
        return v.strip()
    
    @root_validator
    def validate_resolution(cls, values):
        """Validate total pixel count for performance."""
        width = values.get('width', 512)
        height = values.get('height', 512)
        
        max_pixels = 1024 * 1024  # 1MP limit
        if width * height > max_pixels:
            raise ValueError(f"Total resolution {width}x{height} exceeds maximum {max_pixels} pixels")
        
        return values


class SDImg2ImgParams(BaseModel):
    """Stable Diffusion Image-to-Image Parameter."""
    
    image_path: str = Field(
        ...,
        description="Path to input image file",
        example="/artifacts/input.jpg"
    )
    
    prompt: Optional[str] = Field(
        "",
        description="Text prompt for image modification",
        max_length=500,
        example="transform into a painting style"
    )
    
    strength: Optional[float] = Field(
        0.8,
        description="Transformation strength (0.0 = no change, 1.0 = full generation)",
        ge=0.1,
        le=1.0,
        example=0.75
    )
    
    seed: Optional[int] = Field(
        None,
        description="Random seed for reproducible generation",
        ge=0,
        le=2147483647,
        example=42
    )
    
    steps: Optional[int] = Field(
        20,
        description="Number of inference steps",
        ge=10,
        le=50,
        example=20
    )
    
    cfg_scale: Optional[float] = Field(
        7.0,
        description="CFG scale for prompt adherence",
        ge=1.0,
        le=20.0,
        example=7.5,
        alias="cfg"
    )
    
    model: Optional[ImageModel] = Field(
        ImageModel.SD15,
        description="Stable Diffusion model to use",
        example="sd15"
    )
    
    @validator('image_path')
    def validate_image_path(cls, v):
        """Validate image path exists and is valid format."""
        path = Path(v)
        
        if not path.exists():
            raise ValueError(f"Image file not found: {v}")
        
        valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(f"Unsupported image format: {path.suffix}")
        
        # Check file size (max 50MB)
        if path.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("Image file too large (max 50MB)")
        
        return str(path.absolute())


class UpscaleParams(BaseModel):
    """Image Upscaling Parameter."""
    
    image_path: str = Field(
        ...,
        description="Path to input image file",
        example="/artifacts/image.jpg"
    )
    
    scale: UpscaleScale = Field(
        UpscaleScale.X2,
        description="Upscale factor (2x or 4x)",
        example=2
    )
    
    model: Optional[str] = Field(
        "RealESRGAN_x2plus",
        description="Upscaling model to use",
        example="RealESRGAN_x2plus"
    )
    
    @validator('image_path')
    def validate_image_path(cls, v):
        """Validate image path and format."""
        path = Path(v)
        
        if not path.exists():
            raise ValueError(f"Image file not found: {v}")
        
        valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(f"Unsupported image format: {path.suffix}")
        
        # Check file size (max 100MB for upscaling)
        if path.stat().st_size > 100 * 1024 * 1024:
            raise ValueError("Image file too large for upscaling (max 100MB)")
        
        return str(path.absolute())
    
    @root_validator
    def validate_scale_model_compatibility(cls, values):
        """Validate scale factor matches model capabilities."""
        scale = values.get('scale')
        model = values.get('model', 'RealESRGAN_x2plus')
        
        model_scale_map = {
            'RealESRGAN_x2plus': [2],
            'RealESRGAN_x4plus': [4],
            'ESRGAN_x4': [4]
        }
        
        if model in model_scale_map and scale not in model_scale_map[model]:
            raise ValueError(f"Model {model} does not support {scale}x scaling")
        
        return values


class UploadParams(BaseModel):
    """File Upload Parameter."""
    
    path: str = Field(
        ...,
        description="Path to file to upload",
        example="/artifacts/generated_image.jpg"
    )
    
    target: UploadTarget = Field(
        ...,
        description="Upload destination",
        example="telegram"
    )
    
    title: Optional[str] = Field(
        None,
        description="Title for upload (YouTube, etc.)",
        max_length=100,
        example="Generated Image"
    )
    
    description: Optional[str] = Field(
        None,
        description="Description for upload",
        max_length=5000,
        example="AI-generated image using Stable Diffusion"
    )
    
    tags: Optional[List[str]] = Field(
        None,
        description="Tags for categorization",
        max_items=50,
        example=["ai", "generated", "art"]
    )
    
    @validator('path')
    def validate_file_path(cls, v):
        """Validate file exists and is uploadable."""
        path = Path(v)
        
        if not path.exists():
            raise ValueError(f"File not found: {v}")
        
        # Check file size based on target
        max_size = 50 * 1024 * 1024  # 50MB default
        if path.stat().st_size > max_size:
            raise ValueError(f"File too large for upload (max {max_size / 1024 / 1024:.1f}MB)")
        
        return str(path.absolute())
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate tag format."""
        if v:
            for tag in v:
                if len(tag) > 50:
                    raise ValueError(f"Tag too long: {tag}")
                if not tag.replace('_', '').replace('-', '').isalnum():
                    raise ValueError(f"Invalid tag format: {tag}")
        return v


class ASRParams(BaseModel):
    """Automatic Speech Recognition Parameter."""
    
    audio_path: str = Field(
        ...,
        description="Path to audio file",
        example="/uploads/audio.wav"
    )
    
    language: Optional[LanguageCode] = Field(
        LanguageCode.AUTO,
        description="Audio language (auto-detect if not specified)",
        example="de"
    )
    
    model: Optional[str] = Field(
        "whisper-base",
        description="ASR model to use",
        example="whisper-base"
    )
    
    temperature: Optional[float] = Field(
        0.0,
        description="Sampling temperature for ASR",
        ge=0.0,
        le=1.0,
        example=0.0
    )
    
    @validator('audio_path')
    def validate_audio_path(cls, v):
        """Validate audio file."""
        path = Path(v)
        
        if not path.exists():
            raise ValueError(f"Audio file not found: {v}")
        
        valid_extensions = {'.wav', '.mp3', '.m4a', '.flac', '.ogg'}
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(f"Unsupported audio format: {path.suffix}")
        
        # Check file size (max 100MB)
        if path.stat().st_size > 100 * 1024 * 1024:
            raise ValueError("Audio file too large (max 100MB)")
        
        # Check duration estimate (very rough: 1MB ≈ 1 minute)
        estimated_duration_min = path.stat().st_size / (1024 * 1024)
        if estimated_duration_min > 60:  # 1 hour max
            raise ValueError("Audio file too long (max 1 hour)")
        
        return str(path.absolute())


class TTSParams(BaseModel):
    """Text-to-Speech Parameter."""
    
    text: str = Field(
        ...,
        description="Text to convert to speech",
        min_length=1,
        max_length=1000,
        example="Hallo, das ist ein Test der Sprachsynthese."
    )
    
    voice: Optional[VoiceModel] = Field(
        VoiceModel.DE_SPEAKER,
        description="Voice model to use",
        example="de-speaker"
    )
    
    speed: Optional[float] = Field(
        1.0,
        description="Speech speed multiplier",
        ge=0.5,
        le=2.0,
        example=1.0
    )
    
    pitch: Optional[float] = Field(
        1.0,
        description="Pitch multiplier",
        ge=0.5,
        le=2.0,
        example=1.0
    )
    
    emotion: Optional[str] = Field(
        "neutral",
        description="Emotional tone",
        example="happy"
    )
    
    @validator('text')
    def validate_text(cls, v):
        """Validate text content."""
        if not v.strip():
            raise ValueError("Text cannot be empty")
        
        # Basic content filtering
        if len(v.strip()) < 1:
            raise ValueError("Text too short")
        
        # Remove excessive whitespace
        return ' '.join(v.split())
    
    @validator('emotion')
    def validate_emotion(cls, v):
        """Validate emotion values."""
        valid_emotions = {"neutral", "happy", "sad", "angry", "excited", "calm"}
        if v not in valid_emotions:
            raise ValueError(f"Invalid emotion: {v}. Must be one of {valid_emotions}")
        return v


# === OpenAI Function Schema Generator ===

class ToolSchemaGenerator:
    """Generates OpenAI Function schemas from Pydantic models."""
    
    @staticmethod
    def generate_schema(model_class: BaseModel, function_name: str, description: str) -> Dict[str, Any]:
        """Generate OpenAI function schema from Pydantic model."""
        
        # Get Pydantic schema
        pydantic_schema = model_class.schema()
        
        # Convert to OpenAI format
        openai_schema = {
            "type": "function",
            "function": {
                "name": function_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
        
        # Convert properties
        for prop_name, prop_schema in pydantic_schema.get("properties", {}).items():
            openai_schema["function"]["parameters"]["properties"][prop_name] = \
                ToolSchemaGenerator._convert_property(prop_schema)
        
        # Add required fields
        openai_schema["function"]["parameters"]["required"] = \
            pydantic_schema.get("required", [])
        
        return openai_schema
    
    @staticmethod
    def _convert_property(prop_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Pydantic property to OpenAI format."""
        
        result = {}
        
        # Type mapping
        if "type" in prop_schema:
            result["type"] = prop_schema["type"]
        
        # Handle enums
        if "enum" in prop_schema:
            result["enum"] = prop_schema["enum"]
        
        # Constraints
        for constraint in ["minimum", "maximum", "minLength", "maxLength", "pattern"]:
            if constraint in prop_schema:
                result[constraint] = prop_schema[constraint]
        
        # Description and examples
        if "description" in prop_schema:
            result["description"] = prop_schema["description"]
        
        if "example" in prop_schema:
            result["example"] = prop_schema["example"]
        
        # Default values
        if "default" in prop_schema:
            result["default"] = prop_schema["default"]
        
        return result


# === Predefined Tool Schemas ===

def get_core_tool_schemas() -> Dict[str, Dict[str, Any]]:
    """Get all core tool schemas in OpenAI format."""
    
    schemas = {}
    
    # SD Text2Img
    schemas["sd_txt2img"] = ToolSchemaGenerator.generate_schema(
        SDText2ImgParams,
        "sd_txt2img",
        "Generate images from text prompts using Stable Diffusion"
    )
    
    # SD Img2Img
    schemas["sd_img2img"] = ToolSchemaGenerator.generate_schema(
        SDImg2ImgParams,
        "sd_img2img", 
        "Transform existing images based on text prompts using Stable Diffusion"
    )
    
    # Upscale
    schemas["upscale"] = ToolSchemaGenerator.generate_schema(
        UpscaleParams,
        "upscale",
        "Upscale images using AI-based super-resolution models"
    )
    
    # Upload
    schemas["upload"] = ToolSchemaGenerator.generate_schema(
        UploadParams,
        "upload",
        "Upload files to various destinations (Telegram, social media, etc.)"
    )
    
    # ASR
    schemas["asr"] = ToolSchemaGenerator.generate_schema(
        ASRParams,
        "asr",
        "Convert speech to text using automatic speech recognition"
    )
    
    # TTS
    schemas["tts"] = ToolSchemaGenerator.generate_schema(
        TTSParams,
        "tts",
        "Convert text to speech using neural voice synthesis"
    )
    
    return schemas


# === Validation Utilities ===

def validate_tool_params(tool_name: str, params: Dict[str, Any]) -> BaseModel:
    """Validate tool parameters and return typed model."""
    
    model_map = {
        "sd_txt2img": SDText2ImgParams,
        "sd_img2img": SDImg2ImgParams,
        "upscale": UpscaleParams,
        "upload": UploadParams,
        "asr": ASRParams,
        "tts": TTSParams
    }
    
    if tool_name not in model_map:
        raise ValueError(f"Unknown tool: {tool_name}")
    
    model_class = model_map[tool_name]
    
    try:
        return model_class(**params)
    except Exception as e:
        raise ValueError(f"Parameter validation failed for {tool_name}: {str(e)}")


def export_schemas_json(filepath: str = "tool_schemas.json") -> None:
    """Export all schemas to JSON file for external use."""
    
    schemas = get_core_tool_schemas()
    
    with open(filepath, 'w') as f:
        json.dump(schemas, f, indent=2)


if __name__ == "__main__":
    # Demo: Print all schemas
    schemas = get_core_tool_schemas()
    
    for tool_name, schema in schemas.items():
        print(f"\n=== {tool_name.upper()} ===")
        print(json.dumps(schema, indent=2))
    
    # Validation examples
    print("\n=== VALIDATION EXAMPLES ===")
    
    # Valid SD txt2img
    try:
        params = validate_tool_params("sd_txt2img", {
            "prompt": "a beautiful sunset",
            "steps": 25,
            "cfg_scale": 7.5
        })
        print(f"✅ Valid SD params: {params}")
    except ValueError as e:
        print(f"❌ Invalid SD params: {e}")
    
    # Invalid upload target
    try:
        params = validate_tool_params("upload", {
            "path": "/nonexistent/file.jpg",
            "target": "invalid_target"
        })
        print(f"✅ Valid upload params: {params}")
    except ValueError as e:
        print(f"❌ Invalid upload params: {e}")