"""Tests for AI adapters, router, and registry."""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any
import json
import tempfile
import yaml
from pathlib import Path

from ai.adapters import (
    Message,
    MessageRole,
    FunctionDef,
    ToolCall,
    ToolCalls,
    Text,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
    create_provider,
    SchemaRegistry,
    register_model,
    ModelRouter,
    ModelRole,
    RoutingPolicy
)
from ai.adapters.registry import ImageGenerationInput, TextAnalysisInput
from pydantic import BaseModel, Field


# Test Models
class TestToolInput(BaseModel):
    """Test tool input model."""
    query: str = Field(..., description="Test query")
    count: int = Field(10, description="Result count")
    

class ComplexToolInput(BaseModel):
    """Complex nested tool input."""
    name: str
    config: Dict[str, Any]
    items: List[str]
    optional: str = None


# Fixtures
@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for API calls."""
    with patch("httpx.AsyncClient") as mock_client:
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Test response",
                    "tool_calls": None
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        
        # Configure client
        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance
        
        yield mock_instance


@pytest.fixture
def schema_registry():
    """Create a schema registry instance."""
    return SchemaRegistry()


@pytest.fixture
def test_config():
    """Create test configuration."""
    return {
        "models": {
            "planner": {
                "primary": {
                    "provider": "anthropic",
                    "model": "claude-3-sonnet",
                    "temperature": 0.7
                },
                "fallback": [
                    {
                        "provider": "openai",
                        "model": "gpt-4",
                        "temperature": 0.7
                    },
                    {
                        "provider": "ollama",
                        "model": "mixtral",
                        "temperature": 0.7
                    }
                ]
            },
            "exec": {
                "primary": {
                    "provider": "anthropic",
                    "model": "claude-3-opus",
                    "temperature": 0.3
                },
                "fallback": [
                    {
                        "provider": "openai",
                        "model": "gpt-4",
                        "temperature": 0.3
                    },
                    {
                        "provider": "ollama",
                        "model": "codellama",
                        "temperature": 0.3
                    }
                ]
            }
        },
        "routing": {
            "default": "complexity_based",
            "retry": {
                "max_attempts": 2,
                "backoff_factor": 2,
                "initial_delay": 0.1
            }
        },
        "providers": {
            "anthropic": {
                "api_key_env": "ANTHROPIC_API_KEY",
                "base_url": "https://api.anthropic.com/v1"
            },
            "openai": {
                "api_key_env": "OPENAI_API_KEY",
                "base_url": "https://api.openai.com/v1"
            },
            "ollama": {
                "base_url": "http://localhost:11434"
            }
        }
    }


@pytest.fixture
def temp_config_file(test_config):
    """Create temporary config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        yaml.dump(test_config, f)
        config_path = f.name
    
    yield config_path
    
    # Cleanup
    Path(config_path).unlink(missing_ok=True)


# Provider Tests
class TestProviders:
    """Test provider implementations."""
    
    @pytest.mark.asyncio
    async def test_openai_provider(self, mock_httpx_client):
        """Test OpenAI provider chat completion."""
        provider = OpenAIProvider(api_key="test_key")
        
        messages = [
            Message(role=MessageRole.USER, content="Hello")
        ]
        
        result = await provider.achat(messages, model="gpt-4")
        
        assert isinstance(result, Text)
        assert result.content == "Test response"
        mock_httpx_client.post.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_openai_provider_with_tools(self, mock_httpx_client):
        """Test OpenAI provider with tool calling."""
        # Configure mock for tool calls
        mock_httpx_client.post.return_value.json.return_value = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {
                                "name": "test_tool",
                                "arguments": '{"query": "test"}'
                            }
                        }
                    ]
                }
            }]
        }
        
        provider = OpenAIProvider(api_key="test_key")
        
        messages = [
            Message(role=MessageRole.USER, content="Use a tool")
        ]
        
        tools = [
            FunctionDef(
                name="test_tool",
                description="Test tool",
                parameters={"type": "object", "properties": {}}
            )
        ]
        
        result = await provider.achat(messages, tools=tools)
        
        assert isinstance(result, ToolCalls)
        assert len(result.calls) == 1
        assert result.calls[0].name == "test_tool"
        assert result.calls[0].arguments == {"query": "test"}
        
    @pytest.mark.asyncio
    async def test_anthropic_provider(self, mock_httpx_client):
        """Test Anthropic provider chat completion."""
        # Configure mock for Anthropic response
        mock_httpx_client.post.return_value.json.return_value = {
            "content": [{"text": "Claude response"}]
        }
        
        provider = AnthropicProvider(api_key="test_key")
        
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are helpful"),
            Message(role=MessageRole.USER, content="Hello")
        ]
        
        result = await provider.achat(messages, model="claude-3-opus")
        
        assert isinstance(result, Text)
        assert result.content == "Claude response"
        
    @pytest.mark.asyncio
    async def test_ollama_provider(self, mock_httpx_client):
        """Test Ollama provider chat completion."""
        # Configure mock for Ollama response
        mock_httpx_client.post.return_value.json.return_value = {
            "response": "Local model response"
        }
        
        provider = OllamaProvider()
        
        messages = [
            Message(role=MessageRole.USER, content="Hello")
        ]
        
        result = await provider.achat(messages, model="llama2")
        
        assert isinstance(result, Text)
        assert result.content == "Local model response"
        
    def test_create_provider(self):
        """Test provider factory."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}):
            provider = create_provider("openai")
            assert isinstance(provider, OpenAIProvider)
            
        provider = create_provider("anthropic", api_key="test")
        assert isinstance(provider, AnthropicProvider)
        
        provider = create_provider("ollama")
        assert isinstance(provider, OllamaProvider)
        
        with pytest.raises(ValueError):
            create_provider("unknown")


# Registry Tests
class TestSchemaRegistry:
    """Test schema registry functionality."""
    
    def test_register_model(self, schema_registry):
        """Test registering a Pydantic model."""
        func_def = schema_registry.register(
            TestToolInput,
            name="test_tool",
            description="Test tool function",
            version="1.0.0",
            tags=["test", "example"]
        )
        
        assert func_def.name == "test_tool"
        assert func_def.description == "Test tool function"
        assert "query" in func_def.parameters["properties"]
        assert "count" in func_def.parameters["properties"]
        
    def test_register_complex_model(self, schema_registry):
        """Test registering a complex nested model."""
        func_def = schema_registry.register(ComplexToolInput)
        
        assert func_def.name == "complextoolinput"
        assert "name" in func_def.parameters["properties"]
        assert "config" in func_def.parameters["properties"]
        assert "items" in func_def.parameters["properties"]
        assert "optional" in func_def.parameters["properties"]
        assert "name" in func_def.parameters["required"]
        assert "optional" not in func_def.parameters["required"]
        
    def test_version_management(self, schema_registry):
        """Test schema versioning."""
        # Register v1
        func_def_v1 = schema_registry.register(
            TestToolInput,
            name="versioned_tool",
            version="1.0.0"
        )
        
        # Register v2
        func_def_v2 = schema_registry.register(
            ComplexToolInput,
            name="versioned_tool",
            version="2.0.0"
        )
        
        # Get current version
        current = schema_registry.get("versioned_tool")
        assert current == func_def_v2
        
        # Get specific version
        v1 = schema_registry.get("versioned_tool", version="1.0.0")
        assert v1 == func_def_v1
        
    def test_tag_based_retrieval(self, schema_registry):
        """Test getting schemas by tags."""
        schema_registry.register(
            TestToolInput,
            name="tool1",
            tags=["search", "query"]
        )
        
        schema_registry.register(
            ComplexToolInput,
            name="tool2",
            tags=["config", "query"]
        )
        
        # Get by tags
        query_tools = schema_registry.get_by_tags(["query"])
        assert len(query_tools) == 2
        
        search_tools = schema_registry.get_by_tags(["search"])
        assert len(search_tools) == 1
        
    def test_schema_info(self, schema_registry):
        """Test getting schema information."""
        schema_registry.register(
            ImageGenerationInput,
            name="image_gen",
            version="1.0.0",
            tags=["image", "generation"]
        )
        
        info = schema_registry.get_schema_info("image_gen")
        assert info["name"] == "image_gen"
        assert info["current_version"] == "1.0.0"
        assert "image" in info["tags"]
        assert "prompt" in info["function_def"]["parameters"]["properties"]
        
    def test_deprecate_version(self, schema_registry):
        """Test deprecating a schema version."""
        schema_registry.register(
            TestToolInput,
            name="deprecated_test",
            version="1.0.0"
        )
        
        success = schema_registry.deprecate_version("deprecated_test", "1.0.0")
        assert success
        
        info = schema_registry.get_schema_info("deprecated_test")
        assert info["versions"][0]["deprecated"] == True


# Router Tests
class TestModelRouter:
    """Test model router functionality."""
    
    @pytest.fixture
    def mock_providers(self):
        """Mock providers for testing."""
        with patch("ai.adapters.router.create_provider") as mock_create:
            providers = {
                "anthropic": AsyncMock(spec=AnthropicProvider),
                "openai": AsyncMock(spec=OpenAIProvider),
                "ollama": AsyncMock(spec=OllamaProvider)
            }
            
            def create_side_effect(name, **kwargs):
                return providers.get(name)
                
            mock_create.side_effect = create_side_effect
            yield providers
            
    def test_load_config(self, temp_config_file):
        """Test loading configuration from file."""
        router = ModelRouter(config_path=temp_config_file)
        
        assert router.config["models"]["planner"]["primary"]["provider"] == "anthropic"
        assert router.config["models"]["exec"]["primary"]["model"] == "claude-3-opus"
        assert router.current_policy == RoutingPolicy.COMPLEXITY_BASED
        
    def test_default_config(self):
        """Test default configuration when file not found."""
        router = ModelRouter(config_path="nonexistent.yml")
        
        assert "planner" in router.config["models"]
        assert "exec" in router.config["models"]
        assert router.current_policy == RoutingPolicy.COMPLEXITY_BASED
        
    def test_get_model_config(self, temp_config_file):
        """Test getting model configuration."""
        router = ModelRouter(config_path=temp_config_file)
        
        # Get primary planner
        config = router.get_model_config(ModelRole.PLANNER, fallback_level=0)
        assert config.provider == "anthropic"
        assert config.model == "claude-3-sonnet"
        
        # Get first fallback
        config = router.get_model_config(ModelRole.PLANNER, fallback_level=1)
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        
        # Get second fallback
        config = router.get_model_config(ModelRole.PLANNER, fallback_level=2)
        assert config.provider == "ollama"
        assert config.model == "mixtral"
        
    def test_routing_policies(self, temp_config_file, mock_providers):
        """Test different routing policies."""
        router = ModelRouter(config_path=temp_config_file)
        
        # Test default routing
        result = router.route(ModelRole.PLANNER)
        assert result is not None
        assert result.role == ModelRole.PLANNER
        
        # Test cost optimized routing
        router.set_policy(RoutingPolicy.COST_OPTIMIZED)
        result = router.route(ModelRole.EXEC)
        assert result is not None
        
        # Test speed optimized routing
        router.set_policy(RoutingPolicy.SPEED_OPTIMIZED)
        result = router.route(ModelRole.PLANNER)
        assert result is not None
        
    @pytest.mark.asyncio
    async def test_planner_execution(self, temp_config_file, mock_providers):
        """Test planner execution with fallback."""
        router = ModelRouter(config_path=temp_config_file)
        
        # Configure mock response
        mock_providers["anthropic"].achat.return_value = Text(content="Plan created")
        
        messages = [Message(role=MessageRole.USER, content="Create a plan")]
        result = await router.planner(messages)
        
        assert isinstance(result, Text)
        assert result.content == "Plan created"
        mock_providers["anthropic"].achat.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_exec_execution(self, temp_config_file, mock_providers):
        """Test exec execution with fallback."""
        router = ModelRouter(config_path=temp_config_file)
        
        # Configure mock response
        mock_providers["anthropic"].achat.return_value = Text(content="Task executed")
        
        messages = [Message(role=MessageRole.USER, content="Execute task")]
        result = await router.exec(messages)
        
        assert isinstance(result, Text)
        assert result.content == "Task executed"
        mock_providers["anthropic"].achat.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_fallback_cascade(self, temp_config_file, mock_providers):
        """Test fallback cascade on failure."""
        router = ModelRouter(config_path=temp_config_file)
        
        # Configure primary to fail, fallback to succeed
        mock_providers["anthropic"].achat.side_effect = Exception("API Error")
        mock_providers["openai"].achat.return_value = Text(content="Fallback success")
        
        messages = [Message(role=MessageRole.USER, content="Test fallback")]
        result = await router.planner(messages)
        
        assert isinstance(result, Text)
        assert result.content == "Fallback success"
        
        # Primary should be tried twice (retry), then fallback
        assert mock_providers["anthropic"].achat.call_count == 2
        assert mock_providers["openai"].achat.call_count == 1
        
    @pytest.mark.asyncio
    async def test_all_fallbacks_fail(self, temp_config_file, mock_providers):
        """Test when all fallbacks fail."""
        router = ModelRouter(config_path=temp_config_file)
        
        # Configure all to fail
        mock_providers["anthropic"].achat.side_effect = Exception("API Error")
        mock_providers["openai"].achat.side_effect = Exception("API Error")
        mock_providers["ollama"].achat.side_effect = Exception("API Error")
        
        messages = [Message(role=MessageRole.USER, content="Test failure")]
        
        with pytest.raises(RuntimeError) as exc_info:
            await router.planner(messages)
            
        assert "All fallback attempts failed" in str(exc_info.value)
        
    @pytest.mark.asyncio
    async def test_tool_calling(self, temp_config_file, mock_providers):
        """Test router with tool calling."""
        router = ModelRouter(config_path=temp_config_file)
        
        # Configure mock for tool call response
        tool_call = ToolCall(
            id="call_1",
            name="test_tool",
            arguments={"query": "test"}
        )
        mock_providers["anthropic"].achat.return_value = ToolCalls(calls=[tool_call])
        
        messages = [Message(role=MessageRole.USER, content="Use tool")]
        tools = [
            FunctionDef(
                name="test_tool",
                description="Test tool",
                parameters={"type": "object", "properties": {}}
            )
        ]
        
        result = await router.exec(messages, tools=tools)
        
        assert isinstance(result, ToolCalls)
        assert len(result.calls) == 1
        assert result.calls[0].name == "test_tool"


# Integration Tests
class TestIntegration:
    """Test integration between components."""
    
    @pytest.mark.asyncio
    async def test_registry_with_router(self, temp_config_file, mock_providers, schema_registry):
        """Test using registry with router for tool calling."""
        router = ModelRouter(config_path=temp_config_file)
        
        # Register tools
        func_def1 = schema_registry.register(
            ImageGenerationInput,
            name="generate_image",
            tags=["image"]
        )
        
        func_def2 = schema_registry.register(
            TextAnalysisInput,
            name="analyze_text",
            tags=["text"]
        )
        
        # Get tools by tag
        image_tools = schema_registry.get_by_tags(["image"])
        
        # Configure mock response
        mock_providers["anthropic"].achat.return_value = Text(content="Using tools")
        
        # Execute with tools
        messages = [Message(role=MessageRole.USER, content="Generate an image")]
        result = await router.planner(messages, tools=image_tools)
        
        assert isinstance(result, Text)
        
        # Verify tools were passed
        call_args = mock_providers["anthropic"].achat.call_args
        assert call_args[1]["tools"] == image_tools
        
    def test_global_functions(self):
        """Test global convenience functions."""
        from ai.adapters import get_router, get_registry
        
        router1 = get_router()
        router2 = get_router()
        assert router1 is router2  # Singleton
        
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2  # Singleton


if __name__ == "__main__":
    pytest.main([__file__, "-v"])