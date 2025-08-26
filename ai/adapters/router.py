"""Model Router with policy-based selection and fallback cascade."""
import asyncio
import yaml
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from enum import Enum
import time
from dataclasses import dataclass

from ai.adapters.providers import (
    BaseProvider, 
    Message, 
    FunctionDef, 
    ToolCalls, 
    Text,
    create_provider
)
from ai.adapters.registry import get_registry
from core.logging import logger


class ModelRole(str, Enum):
    """Model roles for routing."""
    PLANNER = "planner"
    EXEC = "exec"
    SPECIALIZED = "specialized"


class RoutingPolicy(str, Enum):
    """Available routing policies."""
    COMPLEXITY_BASED = "complexity_based"
    COST_OPTIMIZED = "cost_optimized"
    SPEED_OPTIMIZED = "speed_optimized"


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    provider: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    

@dataclass
class RoutingResult:
    """Result of model routing."""
    provider: BaseProvider
    config: ModelConfig
    role: ModelRole
    fallback_level: int = 0


class ModelRouter:
    """Routes requests to appropriate models based on configuration and policies."""
    
    def __init__(self, config_path: str = "configs/models.yml"):
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.providers: Dict[str, BaseProvider] = {}
        self.current_policy: RoutingPolicy = RoutingPolicy.COMPLEXITY_BASED
        self._load_config()
        self._initialize_providers()
        
    def _load_config(self):
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            self.config = self._get_default_config()
        else:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
                
        # Set default policy
        default_policy = self.config.get("routing", {}).get("default", "complexity_based")
        self.current_policy = RoutingPolicy(default_policy)
        logger.info(f"Loaded model configuration with policy: {self.current_policy}")
        
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if file not found."""
        return {
            "models": {
                "planner": {
                    "primary": {
                        "provider": "openai",
                        "model": "gpt-4-turbo-preview",
                        "temperature": 0.7
                    },
                    "fallback": [
                        {
                            "provider": "ollama",
                            "model": "mixtral:8x7b",
                            "temperature": 0.7
                        }
                    ]
                },
                "exec": {
                    "primary": {
                        "provider": "openai",
                        "model": "gpt-4-turbo-preview",
                        "temperature": 0.3
                    },
                    "fallback": [
                        {
                            "provider": "ollama",
                            "model": "codellama:13b",
                            "temperature": 0.3
                        }
                    ]
                }
            },
            "routing": {
                "default": "complexity_based",
                "retry": {
                    "max_attempts": 3,
                    "backoff_factor": 2,
                    "initial_delay": 1.0
                }
            }
        }
        
    def _initialize_providers(self):
        """Initialize provider instances based on configuration."""
        provider_configs = self.config.get("providers", {})
        
        for provider_name, provider_config in provider_configs.items():
            try:
                # Get API key from environment if specified
                api_key = None
                if "api_key_env" in provider_config:
                    api_key = os.environ.get(provider_config["api_key_env"])
                    
                base_url = provider_config.get("base_url")
                
                # Create provider instance
                provider = create_provider(
                    provider_name,
                    api_key=api_key,
                    base_url=base_url
                )
                self.providers[provider_name] = provider
                logger.info(f"Initialized provider: {provider_name}")
                
            except Exception as e:
                logger.error(f"Failed to initialize provider {provider_name}: {e}")
                
    def set_policy(self, policy: RoutingPolicy):
        """Set the routing policy."""
        self.current_policy = policy
        logger.info(f"Routing policy set to: {policy}")
        
    def get_model_config(self, role: ModelRole, fallback_level: int = 0) -> Optional[ModelConfig]:
        """Get model configuration for a specific role and fallback level."""
        models = self.config.get("models", {})
        role_config = models.get(role.value, {})
        
        if fallback_level == 0:
            # Get primary model
            primary = role_config.get("primary")
            if primary:
                return ModelConfig(**primary)
        else:
            # Get fallback model
            fallbacks = role_config.get("fallback", [])
            if fallback_level - 1 < len(fallbacks):
                return ModelConfig(**fallbacks[fallback_level - 1])
                
        return None
        
    def route(self, role: ModelRole, complexity: Optional[str] = None) -> Optional[RoutingResult]:
        """
        Route to appropriate model based on role and policy.
        
        Args:
            role: Model role (planner, exec, specialized)
            complexity: Optional complexity level (high, medium, low)
            
        Returns:
            RoutingResult with provider and configuration
        """
        # Determine which models to try based on policy
        if self.current_policy == RoutingPolicy.COMPLEXITY_BASED and complexity:
            return self._route_by_complexity(role, complexity)
        elif self.current_policy == RoutingPolicy.COST_OPTIMIZED:
            return self._route_by_cost(role)
        elif self.current_policy == RoutingPolicy.SPEED_OPTIMIZED:
            return self._route_by_speed(role)
        else:
            # Default routing
            return self._route_default(role)
            
    def _route_default(self, role: ModelRole) -> Optional[RoutingResult]:
        """Default routing with fallback cascade."""
        fallback_level = 0
        
        while True:
            config = self.get_model_config(role, fallback_level)
            if not config:
                logger.error(f"No more fallback models for role: {role}")
                return None
                
            provider = self.providers.get(config.provider)
            if provider:
                return RoutingResult(
                    provider=provider,
                    config=config,
                    role=role,
                    fallback_level=fallback_level
                )
                
            fallback_level += 1
            
    def _route_by_complexity(self, role: ModelRole, complexity: str) -> Optional[RoutingResult]:
        """Route based on task complexity."""
        # For now, use default routing
        # In production, would map complexity to specific models
        return self._route_default(role)
        
    def _route_by_cost(self, role: ModelRole) -> Optional[RoutingResult]:
        """Route optimizing for cost (prefer cheaper models)."""
        # Start with highest fallback level (cheapest)
        max_fallback = 5  # Reasonable maximum
        
        for fallback_level in range(max_fallback, -1, -1):
            config = self.get_model_config(role, fallback_level)
            if config:
                provider = self.providers.get(config.provider)
                if provider:
                    return RoutingResult(
                        provider=provider,
                        config=config,
                        role=role,
                        fallback_level=fallback_level
                    )
                    
        return None
        
    def _route_by_speed(self, role: ModelRole) -> Optional[RoutingResult]:
        """Route optimizing for speed (prefer faster models)."""
        # Prefer local models (Ollama) first
        for fallback_level in range(10):  # Check up to 10 levels
            config = self.get_model_config(role, fallback_level)
            if config and config.provider == "ollama":
                provider = self.providers.get(config.provider)
                if provider:
                    return RoutingResult(
                        provider=provider,
                        config=config,
                        role=role,
                        fallback_level=fallback_level
                    )
                    
        # Fall back to default if no local models
        return self._route_default(role)
        
    async def planner(
        self,
        messages: List[Message],
        tools: Optional[List[FunctionDef]] = None,
        **kwargs
    ) -> Union[ToolCalls, Text]:
        """
        Execute planning model with automatic fallback.
        
        Args:
            messages: Chat messages
            tools: Optional tool definitions
            **kwargs: Additional parameters
            
        Returns:
            Model response (ToolCalls or Text)
        """
        return await self._execute_with_fallback(
            ModelRole.PLANNER,
            messages,
            tools,
            **kwargs
        )
        
    async def exec(
        self,
        messages: List[Message],
        tools: Optional[List[FunctionDef]] = None,
        **kwargs
    ) -> Union[ToolCalls, Text]:
        """
        Execute execution model with automatic fallback.
        
        Args:
            messages: Chat messages
            tools: Optional tool definitions
            **kwargs: Additional parameters
            
        Returns:
            Model response (ToolCalls or Text)
        """
        return await self._execute_with_fallback(
            ModelRole.EXEC,
            messages,
            tools,
            **kwargs
        )
        
    async def _execute_with_fallback(
        self,
        role: ModelRole,
        messages: List[Message],
        tools: Optional[List[FunctionDef]] = None,
        **kwargs
    ) -> Union[ToolCalls, Text]:
        """Execute with automatic fallback on failure."""
        retry_config = self.config.get("routing", {}).get("retry", {})
        max_attempts = retry_config.get("max_attempts", 3)
        backoff_factor = retry_config.get("backoff_factor", 2)
        initial_delay = retry_config.get("initial_delay", 1.0)
        
        fallback_level = 0
        last_error = None
        
        while fallback_level < 10:  # Maximum fallback depth
            routing_result = self.route(role)
            if not routing_result:
                break
                
            # Try with retries
            for attempt in range(max_attempts):
                try:
                    logger.info(
                        f"Attempting {role.value} with {routing_result.config.provider}/"
                        f"{routing_result.config.model} (attempt {attempt + 1}/{max_attempts})"
                    )
                    
                    # Merge config parameters with kwargs
                    call_params = {
                        "model": routing_result.config.model,
                        "temperature": routing_result.config.temperature,
                        "max_tokens": routing_result.config.max_tokens,
                        **kwargs
                    }
                    
                    # Add system prompt if specified
                    if routing_result.config.system_prompt:
                        # Prepend system message if not already present
                        if not messages or messages[0].role.value != "system":
                            from ai.adapters.providers import MessageRole
                            system_msg = Message(
                                role=MessageRole.SYSTEM,
                                content=routing_result.config.system_prompt
                            )
                            messages = [system_msg] + messages
                            
                    # Execute
                    result = await routing_result.provider.achat(
                        messages=messages,
                        tools=tools,
                        **call_params
                    )
                    
                    logger.info(f"Successfully executed {role.value}")
                    return result
                    
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {role.value}: {e}"
                    )
                    
                    if attempt < max_attempts - 1:
                        # Wait before retry
                        delay = initial_delay * (backoff_factor ** attempt)
                        await asyncio.sleep(delay)
                        
            # Move to next fallback
            fallback_level += 1
            logger.info(f"Moving to fallback level {fallback_level} for {role.value}")
            
        # All attempts failed
        error_msg = f"All fallback attempts failed for {role.value}"
        if last_error:
            error_msg += f": {last_error}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


# Global router instance
_router: Optional[ModelRouter] = None


def get_router(config_path: Optional[str] = None) -> ModelRouter:
    """Get or create the global router instance."""
    global _router
    if _router is None:
        _router = ModelRouter(config_path or "configs/models.yml")
    return _router


# Convenience functions
async def planner(
    messages: List[Message],
    tools: Optional[List[FunctionDef]] = None,
    **kwargs
) -> Union[ToolCalls, Text]:
    """Execute planner model."""
    router = get_router()
    return await router.planner(messages, tools, **kwargs)


async def exec(
    messages: List[Message],
    tools: Optional[List[FunctionDef]] = None,
    **kwargs
) -> Union[ToolCalls, Text]:
    """Execute execution model."""
    router = get_router()
    return await router.exec(messages, tools, **kwargs)