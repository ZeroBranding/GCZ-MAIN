"""AI Provider Adapters for different LLM services."""
import asyncio
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union, Optional
from dataclasses import dataclass
from enum import Enum
import os

from pydantic import BaseModel, Field
import httpx

from core.logging import logger


class MessageRole(str, Enum):
    """Message roles for chat completion."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """Chat message."""
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


@dataclass
class FunctionDef:
    """Function definition for tool calling."""
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class ToolCall:
    """Tool call request from LLM."""
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolCalls:
    """Collection of tool calls."""
    calls: List[ToolCall]


@dataclass
class Text:
    """Text response from LLM."""
    content: str


class BaseProvider(ABC):
    """Base class for AI providers."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        
    @abstractmethod
    async def achat(
        self, 
        messages: List[Message], 
        tools: Optional[List[FunctionDef]] = None,
        **kwargs
    ) -> Union[ToolCalls, Text]:
        """Async chat completion with optional tool calling."""
        pass
        
    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert Message objects to provider format."""
        return [
            {
                "role": msg.role.value,
                "content": msg.content,
                **({"name": msg.name} if msg.name else {}),
                **({"tool_call_id": msg.tool_call_id} if msg.tool_call_id else {})
            }
            for msg in messages
        ]
        
    def _convert_tools(self, tools: List[FunctionDef]) -> List[Dict[str, Any]]:
        """Convert FunctionDef objects to provider format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            }
            for tool in tools
        ]


class OpenAIProvider(BaseProvider):
    """OpenAI API provider (GPT-4, GPT-3.5, etc.)."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        base_url = base_url or "https://api.openai.com/v1"
        super().__init__(api_key, base_url)
        
    async def achat(
        self, 
        messages: List[Message], 
        tools: Optional[List[FunctionDef]] = None,
        model: str = "gpt-4-turbo-preview",
        temperature: float = 0.7,
        **kwargs
    ) -> Union[ToolCalls, Text]:
        """OpenAI chat completion."""
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": self._convert_messages(messages),
                "temperature": temperature,
                **kwargs
            }
            
            if tools:
                payload["tools"] = self._convert_tools(tools)
                payload["tool_choice"] = "auto"
                
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                choice = data["choices"][0]
                message = choice["message"]
                
                # Check for tool calls
                if "tool_calls" in message and message["tool_calls"]:
                    calls = [
                        ToolCall(
                            id=tc["id"],
                            name=tc["function"]["name"],
                            arguments=json.loads(tc["function"]["arguments"])
                        )
                        for tc in message["tool_calls"]
                    ]
                    return ToolCalls(calls=calls)
                else:
                    return Text(content=message["content"])
                    
            except httpx.HTTPError as e:
                logger.error(f"OpenAI API error: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error in OpenAI provider: {e}")
                raise


class AnthropicProvider(BaseProvider):
    """Anthropic API provider (Claude 3 Opus, Sonnet, etc.)."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        base_url = base_url or "https://api.anthropic.com/v1"
        super().__init__(api_key, base_url)
        
    async def achat(
        self, 
        messages: List[Message], 
        tools: Optional[List[FunctionDef]] = None,
        model: str = "claude-3-opus-20240229",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> Union[ToolCalls, Text]:
        """Anthropic chat completion."""
        async with httpx.AsyncClient() as client:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
            
            # Convert messages to Anthropic format
            anthropic_messages = []
            system_prompt = ""
            
            for msg in messages:
                if msg.role == MessageRole.SYSTEM:
                    system_prompt = msg.content
                else:
                    anthropic_messages.append({
                        "role": "user" if msg.role == MessageRole.USER else "assistant",
                        "content": msg.content
                    })
            
            payload = {
                "model": model,
                "messages": anthropic_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **kwargs
            }
            
            if system_prompt:
                payload["system"] = system_prompt
                
            # Handle tools for Claude (using function calling via prompting)
            if tools:
                tools_prompt = self._create_tools_prompt(tools)
                if anthropic_messages and anthropic_messages[-1]["role"] == "user":
                    anthropic_messages[-1]["content"] += f"\n\n{tools_prompt}"
                    
            try:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                content = data["content"][0]["text"]
                
                # Parse tool calls from response if tools were provided
                if tools and self._contains_tool_call(content):
                    tool_calls = self._parse_tool_calls(content)
                    if tool_calls:
                        return ToolCalls(calls=tool_calls)
                        
                return Text(content=content)
                
            except httpx.HTTPError as e:
                logger.error(f"Anthropic API error: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error in Anthropic provider: {e}")
                raise
                
    def _create_tools_prompt(self, tools: List[FunctionDef]) -> str:
        """Create a prompt describing available tools."""
        tools_desc = "Available tools:\n"
        for tool in tools:
            tools_desc += f"- {tool.name}: {tool.description}\n"
            tools_desc += f"  Parameters: {json.dumps(tool.parameters)}\n"
        tools_desc += "\nTo use a tool, respond with: TOOL_CALL: {\"name\": \"tool_name\", \"arguments\": {...}}"
        return tools_desc
        
    def _contains_tool_call(self, content: str) -> bool:
        """Check if response contains a tool call."""
        return "TOOL_CALL:" in content
        
    def _parse_tool_calls(self, content: str) -> List[ToolCall]:
        """Parse tool calls from response content."""
        tool_calls = []
        if "TOOL_CALL:" in content:
            try:
                # Extract JSON after TOOL_CALL:
                start = content.index("TOOL_CALL:") + len("TOOL_CALL:")
                json_str = content[start:].strip()
                # Find the end of JSON
                if json_str.startswith("{"):
                    end = json_str.index("}") + 1
                    json_str = json_str[:end]
                    
                tool_data = json.loads(json_str)
                tool_calls.append(ToolCall(
                    id=f"call_{len(tool_calls)}",
                    name=tool_data["name"],
                    arguments=tool_data.get("arguments", {})
                ))
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"Failed to parse tool call: {e}")
                
        return tool_calls


class OllamaProvider(BaseProvider):
    """Ollama local model provider."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        # Ollama doesn't need API key
        base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        super().__init__(api_key=None, base_url=base_url)
        
    async def achat(
        self, 
        messages: List[Message], 
        tools: Optional[List[FunctionDef]] = None,
        model: str = "llama2",
        temperature: float = 0.7,
        **kwargs
    ) -> Union[ToolCalls, Text]:
        """Ollama chat completion."""
        async with httpx.AsyncClient() as client:
            # Convert messages to Ollama format
            prompt = self._create_prompt(messages, tools)
            
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    **kwargs.get("options", {})
                }
            }
            
            try:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=60.0  # Longer timeout for local models
                )
                response.raise_for_status()
                
                data = response.json()
                content = data["response"]
                
                # Parse tool calls if tools were provided
                if tools and self._contains_tool_call(content):
                    tool_calls = self._parse_tool_calls(content)
                    if tool_calls:
                        return ToolCalls(calls=tool_calls)
                        
                return Text(content=content)
                
            except httpx.HTTPError as e:
                logger.error(f"Ollama API error: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error in Ollama provider: {e}")
                raise
                
    def _create_prompt(self, messages: List[Message], tools: Optional[List[FunctionDef]]) -> str:
        """Create a prompt from messages and tools."""
        prompt = ""
        
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                prompt += f"System: {msg.content}\n\n"
            elif msg.role == MessageRole.USER:
                prompt += f"User: {msg.content}\n\n"
            elif msg.role == MessageRole.ASSISTANT:
                prompt += f"Assistant: {msg.content}\n\n"
                
        if tools:
            prompt += "Available tools:\n"
            for tool in tools:
                prompt += f"- {tool.name}: {tool.description}\n"
            prompt += "\nTo use a tool, respond with: TOOL_CALL: {\"name\": \"tool_name\", \"arguments\": {...}}\n\n"
            
        prompt += "Assistant: "
        return prompt
        
    def _contains_tool_call(self, content: str) -> bool:
        """Check if response contains a tool call."""
        return "TOOL_CALL:" in content
        
    def _parse_tool_calls(self, content: str) -> List[ToolCall]:
        """Parse tool calls from response content."""
        tool_calls = []
        if "TOOL_CALL:" in content:
            try:
                # Extract JSON after TOOL_CALL:
                start = content.index("TOOL_CALL:") + len("TOOL_CALL:")
                json_str = content[start:].strip()
                # Find the end of JSON
                if json_str.startswith("{"):
                    end = json_str.index("}") + 1
                    json_str = json_str[:end]
                    
                tool_data = json.loads(json_str)
                tool_calls.append(ToolCall(
                    id=f"call_{len(tool_calls)}",
                    name=tool_data["name"],
                    arguments=tool_data.get("arguments", {})
                ))
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"Failed to parse tool call: {e}")
                
        return tool_calls


# Provider factory
def create_provider(provider_type: str, **kwargs) -> BaseProvider:
    """Create a provider instance by type."""
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider
    }
    
    provider_class = providers.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider type: {provider_type}")
        
    return provider_class(**kwargs)