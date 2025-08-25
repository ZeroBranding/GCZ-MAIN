import argparse
import asyncio
import json
import os
from typing import Any, Dict, List

from openai import AsyncOpenAI

from agent.tools_registry import ToolsRegistry
from core.config import RoutingConfig, load_config
from core.errors import ConfigError, EnvError, ExternalToolError
from core.memory import Message

# --- Project Imports ---
from core.logging import logger


class Agent:
    def __init__(self):
        """Initializes the core agent."""
        logger.info("Initializing GCZ Agent...")

        # 1. Load Configuration
        try:
            self.routing_config = load_config('routing', RoutingConfig)
            logger.info(f"Routing config loaded. Planner: {self.routing_config.llm_planner}")
        except Exception as e:
            raise ConfigError(f"Failed to load routing configuration: {e}")

        # 2. Setup Ollama Client
        ollama_host = os.getenv("OLLAMA_HOST")
        if not ollama_host:
            raise EnvError("OLLAMA_HOST environment variable is not set.")

        self.llm_client = AsyncOpenAI(
            base_url=f"{ollama_host}/v1",
            api_key="ollama",  # Required for the library, but not used by Ollama
            # proxies=... # Entfernt, da inkompatibel
        )
        logger.info(f"Ollama client configured for endpoint: {ollama_host}")

        # 3. Setup Tools Registry and load tools from config
        self.tools_registry = ToolsRegistry()
        self.tools_registry.load_from_config()

    async def run_task(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs a specific, predefined task by calling tools in sequence.
        This bypasses the LLM for decision-making for well-known tasks.
        
        Args:
            task (str): The name of the task to run (e.g., "generate_image").
            params (dict): The parameters for the task.
            
        Returns:
            A structured dictionary with status and results.
        """
        logger.info(f"Running predefined task '{task}' with params: {params}")
        artifacts = []
        logs = []

        try:
            if task == "generate_image":
                # Example of a simple, direct tool chain
                prompt_payload = {"json": params} # Assuming params match the tool's expected JSON
                result = self.tools_registry.execute("sd.txt2img", **prompt_payload)
                artifacts.append(result)
                logs.append(f"Successfully triggered image generation with prompt_id: {result.get('prompt_id')}")
            # ... other predefined tasks like "upload_video" could be defined here ...
            else:
                raise NotImplementedError(f"Predefined task '{task}' is not implemented.")

            return {"status": "ok", "artifacts": artifacts, "logs": logs}

        except (KeyError, ExternalToolError, NotImplementedError) as e:
            logger.error(f"Task '{task}' failed: {e}")
            return {"status": "error", "message": str(e), "artifacts": [], "logs": logs}

    async def execute_prompt(self, history: List[Message]) -> str:
        """
        Executes a task based on conversation history, letting the LLM decide.
        """
        if not history:
            return "Ich habe keine Nachricht erhalten, auf die ich antworten kann."

        logger.info(f"Executing conversational prompt with history of {len(history)} messages.")

        # This part of the function would need to be updated to format
        # the ToolsRegistry tools into the OpenAI tool spec format.
        # For this iteration, we focus on the direct `run_task` execution.

        response = await self.llm_client.chat.completions.create(
            model=self.routing_config.llm_planner,
            messages=history,
        )
        final_answer = response.choices[0].message.content
        logger.info(f"LLM direct response: '{final_answer}'")
        return final_answer


async def main():
    """CLI entry point for the agent."""
    parser = argparse.ArgumentParser(description="GCZ Agent CLI")
    parser.add_argument("--task", type=str, required=True, help="The predefined task for the agent to execute.")
    parser.add_argument("--params", type=str, required=True, help="JSON string of parameters for the task.")
    args = parser.parse_args()

    try:
        params_dict = json.loads(args.params)
        agent = Agent()
        result = await agent.run_task(task=args.task, params=params_dict)

        print("\n--- Agent Result ---")
        print(json.dumps(result, indent=2))

    except json.JSONDecodeError:
        logger.error(f"Invalid JSON provided for --params: {args.params}")
    except (ConfigError, EnvError) as e:
        logger.error(f"Configuration Error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)


if __name__ == "__main__":
    # To run: python -m agent.agent --task generate_image --params '{"prompt": "a cat"}'
    asyncio.run(main())
