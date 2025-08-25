import importlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from core.config import BASE_DIR, load_config, ToolsConfig
from core.errors import ConfigError, ExternalToolError
from core.logging import logger


@dataclass
class ToolEndpoint:
    """Represents a callable tool, either via HTTP or in-process Python call."""
    name: str
    method: str  # "POST", "GET", or "PYTHON"
    base_url: Optional[str] = None  # For HTTP endpoints
    path: Optional[str] = None      # For HTTP endpoints
    timeout_s: int = 60
    module: Optional[str] = None    # For PYTHON endpoints, e.g., "services.youtube_service"
    function: Optional[str] = None  # For PYTHON endpoints, e.g., "upload_to_youtube"

class ToolsRegistry:
    """Manages and executes all available tools."""
    _endpoints: Dict[str, ToolEndpoint]

    def __init__(self):
        self._endpoints = {}
        logger.info("ToolsRegistry initialized.")

    def add_endpoint(
        self,
        name: str,
        method: str,
        base_url: Optional[str] = None,
        path: Optional[str] = None,
        module: Optional[str] = None,
        function: Optional[str] = None,
        timeout_s: int = 60,
    ):
        """Programmatically adds or updates a tool endpoint."""
        endpoint = ToolEndpoint(
            name=name,
            method=method.upper(),
            base_url=base_url,
            path=path,
            module=module,
            function=function,
            timeout_s=timeout_s,
        )
        self._endpoints[name] = endpoint
        logger.debug(f"Added/updated tool endpoint: {name}")

    def has(self, name: str) -> bool:
        """Checks if a tool with the given name is registered."""
        return name in self._endpoints

    def get(self, name: str) -> Optional[ToolEndpoint]:
        """Retrieves a tool endpoint by name."""
        return self._endpoints.get(name)

    def load_from_config(self):
        """Loads tool endpoints from configs/tools.yml."""
        config_path = BASE_DIR / "configs" / "tools.yml"
        if not config_path.exists():
            logger.warning(f"Tools config file not found at {config_path}. No tools loaded.")
            return

        try:
            tools_config = load_config('tools', ToolsConfig)
            tool_endpoints = tools_config.tool_endpoints
            for tool_conf in tool_endpoints:
                self.add_endpoint(**tool_conf.model_dump())
            logger.info(f"Loaded {len(tool_endpoints)} tool(s) from {config_path}.")
        except Exception as e:
            raise ConfigError(f"Failed to load or parse tools.yml: {e}")

    def execute(self, name: str, **kwargs: Any) -> Any:
        """
        Executes a tool by its registered name with the given arguments.
        
        Raises:
            KeyError: If the tool is not found.
            ExternalToolError: For errors during execution (HTTP or Python).
        """
        if not self.has(name):
            raise KeyError(f"Tool '{name}' not found in registry.")

        endpoint = self.get(name)
        logger.info(f"Executing tool '{name}' (type: {endpoint.method})...")

        if endpoint.method in ["POST", "GET"]:
            return self._execute_http(endpoint, **kwargs)
        elif endpoint.method == "PYTHON":
            return self._execute_python(endpoint, **kwargs)
        else:
            raise NotImplementedError(f"Execution method '{endpoint.method}' is not supported.")

    def _execute_http(self, endpoint: ToolEndpoint, **kwargs: Any) -> Dict[str, Any]:
        """Handles HTTP-based tool execution."""
        if not endpoint.base_url or not endpoint.path:
            raise ConfigError(f"HTTP endpoint '{endpoint.name}' is missing base_url or path.")

        # Substitute path parameters like {id}
        url = f"{endpoint.base_url.rstrip('/')}{endpoint.path.format(**kwargs)}"

        json_payload = kwargs.get('json', {})

        try:
            if endpoint.method == "POST":
                response = requests.post(url, json=json_payload, timeout=endpoint.timeout_s)
            else: # GET
                response = requests.get(url, timeout=endpoint.timeout_s)

            response.raise_for_status()  # Raises HTTPError for 4xx/5xx status

            # Return JSON response or a success stub if no content
            return response.json() if response.content else {"status": "ok"}

        except requests.exceptions.Timeout:
            raise ExternalToolError(f"Tool '{endpoint.name}' timed out after {endpoint.timeout_s}s.")
        except requests.exceptions.RequestException as e:
            raise ExternalToolError(f"Tool '{endpoint.name}' failed: {e}")

    def _execute_python(self, endpoint: ToolEndpoint, **kwargs: Any) -> Any:
        """Handles in-process Python tool execution."""
        if not endpoint.module or not endpoint.function:
            raise ConfigError(f"Python endpoint '{endpoint.name}' is missing module or function.")

        try:
            mod = importlib.import_module(endpoint.module)
            func = getattr(mod, endpoint.function)

            # Here we could instantiate a class if the module contains a service class
            # For simplicity, we assume direct function calls for now.

            return func(**kwargs)

        except (ImportError, AttributeError) as e:
            raise ConfigError(f"Could not load Python tool '{endpoint.name}': {e}")
        except Exception as e:
            # Catch exceptions from the tool's execution itself
            raise ExternalToolError(f"Python tool '{endpoint.name}' execution failed: {e}")
