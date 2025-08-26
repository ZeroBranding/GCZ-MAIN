# Toolkit Adapter Specification

## Overview

Minimal-invasive Tool-Abstraction für einheitliche Integration verschiedener Services und External APIs. Ermöglicht dynamische Tool-Discovery, Schema-Versionierung und konsistente Error-Handling.

## Core Interfaces

### ToolBase Interface

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum
import time

class ToolResultStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    INVALID_INPUT = "invalid_input"

@dataclass
class ToolResult:
    """Unified tool execution result envelope."""
    status: ToolResultStatus
    value: Any = None
    error: Optional[str] = None
    latency_ms: int = 0
    cost_usd: Optional[float] = None
    metadata: Dict[str, Any] = None
    
    # Performance tracking
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def __post_init__(self):
        if self.completed_at and self.started_at:
            self.latency_ms = int((self.completed_at - self.started_at) * 1000)
    
    @classmethod
    def success(cls, value: Any, **kwargs) -> 'ToolResult':
        """Creates success result."""
        return cls(status=ToolResultStatus.SUCCESS, value=value, **kwargs)
    
    @classmethod 
    def error(cls, error: str, **kwargs) -> 'ToolResult':
        """Creates error result."""
        return cls(status=ToolResultStatus.ERROR, error=error, **kwargs)
    
    @classmethod
    def timeout(cls, **kwargs) -> 'ToolResult':
        """Creates timeout result."""
        return cls(status=ToolResultStatus.TIMEOUT, error="Operation timed out", **kwargs)

class ToolBase(ABC):
    """Base interface für alle Tools."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = self.get_name()
        self.version = self.get_version()
    
    @abstractmethod
    def get_name(self) -> str:
        """Tool name (must be unique)."""
        pass
    
    @abstractmethod
    def get_version(self) -> str:
        """Tool version (semver)."""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Human-readable tool description."""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """OpenAI function schema for tool."""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute tool with given parameters."""
        pass
    
    @abstractmethod
    async def validate_input(self, **kwargs) -> bool:
        """Validate input parameters before execution."""
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Tool capabilities metadata."""
        return {
            "async": True,
            "streaming": False,
            "batch": False,
            "cost_tracking": False,
            "rate_limited": False
        }
    
    async def health_check(self) -> bool:
        """Check if tool is operational."""
        return True
    
    def get_cost_estimate(self, **kwargs) -> Optional[float]:
        """Estimate execution cost in USD."""
        return None
```

### Schema Registry

```python
from pydantic import BaseModel
from typing import Type, Dict, List, Callable

class ToolSchema(BaseModel):
    """Pydantic model für Tool-Schema-Definition."""
    name: str
    version: str
    description: str
    parameters: Dict[str, Any]
    required: List[str] = []
    returns: Dict[str, Any] = {}
    examples: List[Dict[str, Any]] = []
    
class SchemaRegistry:
    """Registry für Tool-Schema-Management und Versionierung."""
    
    def __init__(self):
        self._schemas: Dict[str, Dict[str, ToolSchema]] = {}
        self._tools: Dict[str, Dict[str, ToolBase]] = {}
        self._converters: Dict[str, Callable] = {}
    
    def register_tool(self, tool: ToolBase) -> None:
        """Registriert Tool mit automatischer Schema-Generierung."""
        pass
    
    def register_schema(self, schema: ToolSchema) -> None:
        """Registriert Schema manuell."""
        pass
    
    def get_tool(self, name: str, version: str = "latest") -> Optional[ToolBase]:
        """Holt Tool-Instanz."""
        pass
    
    def get_schema(self, name: str, version: str = "latest") -> Optional[ToolSchema]:
        """Holt Tool-Schema."""
        pass
    
    def get_openai_schema(self, name: str, version: str = "latest") -> Optional[Dict[str, Any]]:
        """Konvertiert zu OpenAI Function-Schema."""
        pass
    
    def list_tools(self, category: Optional[str] = None) -> List[str]:
        """Listet verfügbare Tools."""
        pass
    
    def validate_compatibility(self, name: str, old_version: str, new_version: str) -> bool:
        """Prüft Schema-Kompatibilität zwischen Versionen."""
        pass

# Decorator für automatische Tool-Registrierung
def register_tool(registry: SchemaRegistry, category: str = None):
    """Decorator für automatische Tool-Registrierung."""
    def decorator(tool_class: Type[ToolBase]):
        # Auto-registration logic
        return tool_class
    return decorator
```

### Tool Categories

```python
class ToolCategory(str, Enum):
    """Kategorien für Tool-Organisation."""
    IMAGE_GENERATION = "image_generation"
    IMAGE_PROCESSING = "image_processing" 
    VIDEO_CREATION = "video_creation"
    AUDIO_PROCESSING = "audio_processing"
    SOCIAL_MEDIA = "social_media"
    COMMUNICATION = "communication"
    ANALYSIS = "analysis"
    UTILITY = "utility"
    EXTERNAL_API = "external_api"

@dataclass
class ToolMetadata:
    """Extended metadata für Tools."""
    category: ToolCategory
    tags: List[str] = []
    dependencies: List[str] = []
    min_python_version: str = "3.11"
    requires_gpu: bool = False
    requires_internet: bool = False
    rate_limits: Dict[str, int] = None  # {"requests_per_minute": 60}
    estimated_latency_ms: Optional[int] = None
    typical_cost_usd: Optional[float] = None
```

## Tool Implementations

### Service Tool Adapter

```python
class ServiceToolAdapter(ToolBase):
    """Adapter für bestehende Services zu Tool-Interface."""
    
    def __init__(self, service_instance, method_name: str, config: Dict[str, Any] = None):
        super().__init__(config)
        self.service = service_instance
        self.method = method_name
        self._schema_cache = None
    
    def get_name(self) -> str:
        return f"{self.service.__class__.__name__.lower()}_{self.method}"
    
    def get_version(self) -> str:
        return getattr(self.service, '__version__', '1.0.0')
    
    def get_description(self) -> str:
        method = getattr(self.service, self.method)
        return method.__doc__ or f"Execute {self.method} on {self.service.__class__.__name__}"
    
    def get_schema(self) -> Dict[str, Any]:
        """Auto-generate schema from service method signature."""
        if self._schema_cache is None:
            self._schema_cache = self._generate_schema_from_method()
        return self._schema_cache
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute service method with error handling."""
        start_time = time.time()
        
        try:
            method = getattr(self.service, self.method)
            
            # Handle sync/async methods
            if asyncio.iscoroutinefunction(method):
                result = await method(**kwargs)
            else:
                result = method(**kwargs)
            
            return ToolResult.success(
                value=result,
                started_at=start_time,
                completed_at=time.time()
            )
            
        except Exception as e:
            return ToolResult.error(
                error=str(e),
                started_at=start_time,
                completed_at=time.time(),
                metadata={"exception_type": type(e).__name__}
            )
```

### External API Tool

```python
class ExternalAPITool(ToolBase):
    """Base for external API integrations."""
    
    def __init__(self, api_key: str, base_url: str, config: Dict[str, Any] = None):
        super().__init__(config)
        self.api_key = api_key
        self.base_url = base_url
        self.session = None
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> ToolResult:
        """Unified HTTP request handling."""
        import aiohttp
        
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        start_time = time.time()
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with self.session.request(
                method,
                f"{self.base_url}/{endpoint}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.config.get('timeout_s', 60)),
                **kwargs
            ) as response:
                
                if response.status == 429:
                    return ToolResult(
                        status=ToolResultStatus.RATE_LIMITED,
                        error="Rate limit exceeded",
                        started_at=start_time,
                        completed_at=time.time()
                    )
                
                response.raise_for_status()
                data = await response.json()
                
                return ToolResult.success(
                    value=data,
                    started_at=start_time,
                    completed_at=time.time()
                )
                
        except asyncio.TimeoutError:
            return ToolResult.timeout(
                started_at=start_time,
                completed_at=time.time()
            )
        except Exception as e:
            return ToolResult.error(
                error=str(e),
                started_at=start_time,
                completed_at=time.time()
            )
```

## Concrete Tool Examples

### SD Text2Img Tool

```python
@register_tool(registry, category="image_generation")
class SDText2ImgTool(ToolBase):
    """Stable Diffusion Text-to-Image Tool."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        from services.sd_service import SDService
        self.sd_service = SDService()
    
    def get_name(self) -> str:
        return "sd_txt2img"
    
    def get_version(self) -> str:
        return "2.1.0"
    
    def get_description(self) -> str:
        return "Generate images from text prompts using Stable Diffusion"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "sd_txt2img",
                "description": self.get_description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Text prompt for image generation"
                        },
                        "width": {
                            "type": "integer",
                            "default": 512,
                            "minimum": 256,
                            "maximum": 1024
                        },
                        "height": {
                            "type": "integer", 
                            "default": 512,
                            "minimum": 256,
                            "maximum": 1024
                        },
                        "steps": {
                            "type": "integer",
                            "default": 20,
                            "minimum": 10,
                            "maximum": 50
                        }
                    },
                    "required": ["prompt"]
                }
            }
        }
    
    async def validate_input(self, **kwargs) -> bool:
        """Validate input parameters."""
        prompt = kwargs.get('prompt', '')
        if not prompt or len(prompt.strip()) == 0:
            return False
        
        width = kwargs.get('width', 512)
        height = kwargs.get('height', 512)
        
        if width < 256 or width > 1024 or height < 256 or height > 1024:
            return False
            
        return True
    
    async def execute(self, **kwargs) -> ToolResult:
        """Execute image generation."""
        if not await self.validate_input(**kwargs):
            return ToolResult.error("Invalid input parameters")
        
        start_time = time.time()
        
        try:
            image_path = await self.sd_service.txt2img(
                prompt=kwargs['prompt'],
                width=kwargs.get('width', 512),
                height=kwargs.get('height', 512),
                steps=kwargs.get('steps', 20)
            )
            
            return ToolResult.success(
                value={"image_path": str(image_path)},
                started_at=start_time,
                completed_at=time.time(),
                metadata={
                    "file_size_bytes": image_path.stat().st_size if image_path.exists() else 0,
                    "prompt": kwargs['prompt']
                }
            )
            
        except Exception as e:
            return ToolResult.error(
                error=f"Image generation failed: {str(e)}",
                started_at=start_time,
                completed_at=time.time()
            )
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "async": True,
            "streaming": False,
            "batch": False,
            "cost_tracking": True,
            "rate_limited": True,
            "requires_gpu": True
        }
    
    def get_cost_estimate(self, **kwargs) -> Optional[float]:
        """Estimate GPU cost based on parameters."""
        steps = kwargs.get('steps', 20)
        resolution = kwargs.get('width', 512) * kwargs.get('height', 512)
        
        # Simple cost model: base cost + step cost + resolution cost
        base_cost = 0.01  # $0.01 base
        step_cost = steps * 0.0005  # $0.0005 per step
        resolution_cost = (resolution / (512 * 512)) * 0.005  # Resolution multiplier
        
        return base_cost + step_cost + resolution_cost
```

### Email Tool

```python
@register_tool(registry, category="communication")
class EmailTool(ToolBase):
    """Email sending tool."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        from services.email_service import EmailService
        self.email_service = EmailService('gmail')  # From config
    
    def get_name(self) -> str:
        return "send_email"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_description(self) -> str:
        return "Send email via configured email service"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "send_email",
                "description": self.get_description(),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Recipient email address"
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject"
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body text"
                        },
                        "attachments": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of file paths to attach"
                        }
                    },
                    "required": ["to", "subject", "body"]
                }
            }
        }
    
    async def validate_input(self, **kwargs) -> bool:
        import re
        
        to_email = kwargs.get('to', '')
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        return bool(re.match(email_pattern, to_email))
    
    async def execute(self, **kwargs) -> ToolResult:
        start_time = time.time()
        
        try:
            message_id = await self.email_service.send_email(
                to=kwargs['to'],
                subject=kwargs['subject'],
                body=kwargs['body'],
                attachments=kwargs.get('attachments', [])
            )
            
            return ToolResult.success(
                value={"message_id": message_id},
                started_at=start_time,
                completed_at=time.time()
            )
            
        except Exception as e:
            return ToolResult.error(
                error=str(e),
                started_at=start_time,
                completed_at=time.time()
            )
```

## Tool Execution Engine

### ToolExecutor

```python
class ToolExecutor:
    """Executes tools with consistent error handling and monitoring."""
    
    def __init__(self, registry: SchemaRegistry):
        self.registry = registry
        self.metrics = {}
        self.circuit_breakers = {}
    
    async def execute_tool(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> ToolResult:
        """Execute tool with full monitoring and error handling."""
        
        # Get tool instance
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return ToolResult.error(f"Tool '{tool_name}' not found")
        
        # Check circuit breaker
        if self._is_circuit_open(tool_name):
            return ToolResult.error(f"Circuit breaker open for '{tool_name}'")
        
        # Validate input
        try:
            if not await tool.validate_input(**parameters):
                return ToolResult.error("Input validation failed")
        except Exception as e:
            return ToolResult.error(f"Input validation error: {str(e)}")
        
        # Execute with timeout
        try:
            timeout = self._get_tool_timeout(tool_name)
            result = await asyncio.wait_for(
                tool.execute(**parameters),
                timeout=timeout
            )
            
            # Record success metrics
            self._record_success(tool_name, result)
            
            return result
            
        except asyncio.TimeoutError:
            result = ToolResult.timeout()
            self._record_failure(tool_name, "timeout")
            return result
            
        except Exception as e:
            result = ToolResult.error(str(e))
            self._record_failure(tool_name, "exception")
            return result
    
    def _is_circuit_open(self, tool_name: str) -> bool:
        """Check if circuit breaker is open for tool."""
        # Circuit breaker implementation
        return False
    
    def _get_tool_timeout(self, tool_name: str) -> float:
        """Get timeout for specific tool."""
        # Tool-specific timeout logic
        return 60.0
    
    def _record_success(self, tool_name: str, result: ToolResult) -> None:
        """Record successful execution metrics."""
        pass
    
    def _record_failure(self, tool_name: str, failure_type: str) -> None:
        """Record failure metrics."""
        pass
```

## Integration with LangGraph

### Tool Integration für bestehende Nodes

```python
# Minimal integration in ExecutorNode
class ExecutorNode:
    def __init__(self):
        # Bestehende Initialisierung
        super().__init__()
        
        # Neu: Tool-System (optional)
        self.tool_registry = SchemaRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        
        # Auto-register bestehende Services
        self._register_existing_services()
    
    def _register_existing_services(self):
        """Registriert bestehende Services als Tools."""
        try:
            from services.sd_service import SDService
            sd_tool = ServiceToolAdapter(SDService(), 'txt2img')
            self.tool_registry.register_tool(sd_tool)
        except ImportError:
            pass  # Service nicht verfügbar
    
    async def _execute_step(self, step_item: PlanItem, state: GraphState) -> Dict:
        """Enhanced step execution mit Tool-System."""
        
        # Versuche Tool-System (neue Features)
        if self.tool_registry.get_tool(step_item.action):
            return await self._execute_via_tools(step_item, state)
        
        # Fallback: bestehende Service-Mappings (backwards compatibility)
        return await self._execute_via_services(step_item, state)
    
    async def _execute_via_tools(self, step_item: PlanItem, state: GraphState) -> Dict:
        """Execute via unified tool system."""
        result = await self.tool_executor.execute_tool(
            tool_name=step_item.action,
            parameters=step_item.params,
            context={"session_id": state.session_id}
        )
        
        if result.status == ToolResultStatus.SUCCESS:
            return {
                'success': True,
                'artifacts': [result.value.get('image_path')] if 'image_path' in result.value else [],
                'output_data': result.value,
                'latency_ms': result.latency_ms,
                'cost_usd': result.cost_usd
            }
        else:
            return {
                'success': False,
                'error': result.error
            }
```

## Backwards Compatibility

### Gradual Migration Strategy

```python
# Feature flag für Tool-System
class ToolSystemConfig:
    enable_tool_system: bool = False
    fallback_to_services: bool = True
    tool_categories: List[str] = ["image_generation", "communication"]

# Wrapper für bestehende Services
def create_service_tools(registry: SchemaRegistry) -> None:
    """Automatische Tool-Erstellung für bestehende Services."""
    
    service_mappings = [
        ('services.sd_service', 'SDService', ['txt2img', 'img2img', 'upscale']),
        ('services.email_service', 'EmailService', ['send_email', 'list_emails']),
        ('services.voice_service', 'VoiceService', ['text_to_speech']),
        # ... weitere Services
    ]
    
    for module_path, class_name, methods in service_mappings:
        try:
            module = importlib.import_module(module_path)
            service_class = getattr(module, class_name)
            
            for method in methods:
                tool = ServiceToolAdapter(service_class(), method)
                registry.register_tool(tool)
                
        except (ImportError, AttributeError):
            # Service nicht verfügbar, skip
            continue
```

Diese Spezifikation bietet **minimal-invasive Tool-Integration** mit vollständiger **Backwards-Compatibility** zum bestehenden Code!