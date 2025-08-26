"""Tools module - Pydantic models and OpenAI function schema conversion."""
from typing import Dict, Any, List, Optional, Type, Callable
from pydantic import BaseModel, Field, validator
from enum import Enum
import json
import inspect

from core.logging import logger

# Tool parameter models
class ImageGenerationParams(BaseModel):
    """Parameters for image generation."""
    prompt: str = Field(..., description="Text prompt for image generation")
    width: int = Field(512, description="Image width in pixels", ge=128, le=2048)
    height: int = Field(512, description="Image height in pixels", ge=128, le=2048)
    model: str = Field("stable-diffusion", description="Model to use for generation")
    seed: Optional[int] = Field(None, description="Random seed for reproducibility")
    
    @validator("prompt")
    def validate_prompt(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Prompt cannot be empty")
        if len(v) > 1000:
            raise ValueError("Prompt too long (max 1000 characters)")
        return v.strip()

class UpscaleParams(BaseModel):
    """Parameters for image upscaling."""
    input_path: str = Field(..., description="Path to input image")
    scale: int = Field(2, description="Upscale factor", ge=2, le=4)
    model: str = Field("esrgan", description="Upscaling model")
    
class AnimationParams(BaseModel):
    """Parameters for animation generation."""
    prompt: str = Field(..., description="Text prompt for animation")
    duration: float = Field(3.0, description="Animation duration in seconds", ge=1.0, le=10.0)
    fps: int = Field(24, description="Frames per second", ge=8, le=60)
    style: str = Field("default", description="Animation style")

class ServiceType(str, Enum):
    """Available service types."""
    SD_SERVICE = "sd_service"
    ANIM_SERVICE = "anim_service"
    VOICE_SERVICE = "voice_service"
    ASR_SERVICE = "asr_service"
    TELEGRAM_SERVICE = "telegram_service"

class ServiceCallParams(BaseModel):
    """Generic parameters for service calls."""
    service: ServiceType = Field(..., description="Service to call")
    method: str = Field(..., description="Method name to invoke")
    params: Dict[str, Any] = Field(default_factory=dict, description="Method parameters")

# Tool definitions
class Tool(BaseModel):
    """Base class for tool definitions."""
    name: str
    description: str
    parameters_model: Type[BaseModel]
    handler: Optional[Callable] = None
    
    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function schema format."""
        schema = self.parameters_model.model_json_schema()
        
        # Convert Pydantic schema to OpenAI format
        openai_schema = {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
        
        # Process properties
        if "properties" in schema:
            for prop_name, prop_schema in schema["properties"].items():
                # Simplify schema for OpenAI
                simplified = self._simplify_schema(prop_schema)
                openai_schema["parameters"]["properties"][prop_name] = simplified
                
        # Add required fields
        if "required" in schema:
            openai_schema["parameters"]["required"] = schema["required"]
            
        return openai_schema
        
    def _simplify_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Simplify Pydantic schema for OpenAI."""
        simplified = {}
        
        # Copy basic fields
        for key in ["type", "description", "enum", "default"]:
            if key in schema:
                simplified[key] = schema[key]
                
        # Handle numeric constraints
        if schema.get("type") in ["integer", "number"]:
            for constraint in ["minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"]:
                if constraint in schema:
                    simplified[constraint] = schema[constraint]
                    
        # Handle string constraints
        if schema.get("type") == "string":
            for constraint in ["minLength", "maxLength", "pattern"]:
                if constraint in schema:
                    simplified[constraint] = schema[constraint]
                    
        return simplified
        
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters."""
        # Validate parameters
        try:
            params = self.parameters_model(**kwargs)
        except Exception as e:
            logger.error(f"Parameter validation failed for {self.name}: {e}")
            raise ValueError(f"Invalid parameters: {e}")
            
        # Execute handler if available
        if self.handler:
            return await self.handler(params)
        else:
            return {"status": "no_handler", "params": params.model_dump()}

# Tool registry
class ToolRegistry:
    """Registry for available tools."""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()
        
    def _register_default_tools(self):
        """Register default tools."""
        # Image generation tool
        self.register(Tool(
            name="generate_image",
            description="Generate an image from text prompt",
            parameters_model=ImageGenerationParams,
            handler=self._generate_image_handler
        ))
        
        # Upscale tool
        self.register(Tool(
            name="upscale_image",
            description="Upscale an image to higher resolution",
            parameters_model=UpscaleParams,
            handler=self._upscale_handler
        ))
        
        # Animation tool
        self.register(Tool(
            name="generate_animation",
            description="Generate an animation from text prompt",
            parameters_model=AnimationParams,
            handler=self._animation_handler
        ))
        
        # Generic service call tool
        self.register(Tool(
            name="call_service",
            description="Call a service method",
            parameters_model=ServiceCallParams,
            handler=self._service_call_handler
        ))
        
    def register(self, tool: Tool):
        """Register a new tool."""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
        
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self.tools.get(name)
        
    def list_tools(self) -> List[str]:
        """List all available tool names."""
        return list(self.tools.keys())
        
    def get_openai_schemas(self) -> List[Dict[str, Any]]:
        """Get OpenAI function schemas for all tools."""
        return [tool.to_openai_schema() for tool in self.tools.values()]
        
    async def execute_tool(self, name: str, **kwargs) -> Dict[str, Any]:
        """Execute a tool by name."""
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        return await tool.execute(**kwargs)
        
    # Tool handlers
    async def _generate_image_handler(self, params: ImageGenerationParams) -> Dict[str, Any]:
        """Handler for image generation."""
        from services.sd_service import SDService
        
        try:
            sd_service = SDService()
            image_path = await sd_service.generate_image(
                prompt=params.prompt,
                width=params.width,
                height=params.height
            )
            return {
                "status": "success",
                "image_path": image_path,
                "params": params.model_dump()
            }
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "params": params.model_dump()
            }
            
    async def _upscale_handler(self, params: UpscaleParams) -> Dict[str, Any]:
        """Handler for image upscaling."""
        # In production, would call actual upscaling service
        return {
            "status": "success",
            "output_path": f"{params.input_path.replace('.png', '_upscaled.png')}",
            "scale": params.scale,
            "params": params.model_dump()
        }
        
    async def _animation_handler(self, params: AnimationParams) -> Dict[str, Any]:
        """Handler for animation generation."""
        from services.anim_service import AnimService
        
        try:
            anim_service = AnimService()
            animation_path = await anim_service.generate_animation(
                prompt=params.prompt,
                duration=params.duration
            )
            return {
                "status": "success",
                "animation_path": animation_path,
                "params": params.model_dump()
            }
        except Exception as e:
            logger.error(f"Animation generation failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "params": params.model_dump()
            }
            
    async def _service_call_handler(self, params: ServiceCallParams) -> Dict[str, Any]:
        """Handler for generic service calls."""
        # Map service names to actual service modules
        service_map = {
            ServiceType.SD_SERVICE: "services.sd_service.SDService",
            ServiceType.ANIM_SERVICE: "services.anim_service.AnimService",
            ServiceType.VOICE_SERVICE: "services.voice_service.VoiceService",
            ServiceType.ASR_SERVICE: "services.asr_service.ASRService",
            ServiceType.TELEGRAM_SERVICE: "services.telegram_service.TelegramService",
        }
        
        try:
            # Import and instantiate service
            module_path, class_name = service_map[params.service].rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            service_class = getattr(module, class_name)
            service_instance = service_class()
            
            # Get method
            method = getattr(service_instance, params.method, None)
            if not method:
                raise AttributeError(f"Method {params.method} not found in {params.service}")
                
            # Call method
            if inspect.iscoroutinefunction(method):
                result = await method(**params.params)
            else:
                result = method(**params.params)
                
            return {
                "status": "success",
                "result": result,
                "service": params.service,
                "method": params.method
            }
        except Exception as e:
            logger.error(f"Service call failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "service": params.service,
                "method": params.method
            }

# Global registry instance
_registry = ToolRegistry()

def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _registry

# Convenience functions
def register_tool(tool: Tool):
    """Register a tool in the global registry."""
    _registry.register(tool)
    
def get_tool(name: str) -> Optional[Tool]:
    """Get a tool from the global registry."""
    return _registry.get(name)
    
async def execute_tool(name: str, **kwargs) -> Dict[str, Any]:
    """Execute a tool from the global registry."""
    return await _registry.execute_tool(name, **kwargs)
    
def get_openai_tools() -> List[Dict[str, Any]]:
    """Get OpenAI function schemas for all registered tools."""
    return _registry.get_openai_schemas()