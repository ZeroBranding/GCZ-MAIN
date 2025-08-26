"""AI Adapters module for provider abstraction and routing."""
from ai.adapters.providers import (
    BaseProvider,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
    Message,
    MessageRole,
    FunctionDef,
    ToolCall,
    ToolCalls,
    Text,
    create_provider
)

from ai.adapters.registry import (
    SchemaRegistry,
    get_registry,
    register_model,
    get_function_def,
    get_functions_by_tags
)

from ai.adapters.router import (
    ModelRouter,
    ModelRole,
    RoutingPolicy,
    get_router,
    planner,
    exec
)

__all__ = [
    # Providers
    "BaseProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "Message",
    "MessageRole",
    "FunctionDef",
    "ToolCall",
    "ToolCalls",
    "Text",
    "create_provider",
    
    # Registry
    "SchemaRegistry",
    "get_registry",
    "register_model",
    "get_function_def",
    "get_functions_by_tags",
    
    # Router
    "ModelRouter",
    "ModelRole",
    "RoutingPolicy",
    "get_router",
    "planner",
    "exec"
]