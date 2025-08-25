import os

# Add project root to path to allow direct script execution
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import asyncio

sys.path.append(str(Path(__file__).resolve().parent.parent))

from agent.agent import Agent
from core.errors import ExternalToolError


class TestAgent(unittest.TestCase):

    @patch('agent.agent.ToolsRegistry')
    @patch('agent.agent.AsyncOpenAI')
    @patch('agent.agent.load_config')
    def setUp(self, mock_load_config, mock_async_openai, mock_tools_registry):
        """Set up the agent with mocked dependencies."""
        os.environ['OLLAMA_HOST'] = 'http://mock-ollama'
        self.mock_registry_instance = mock_tools_registry.return_value
        self.agent = Agent()

    def tearDown(self):
        del os.environ['OLLAMA_HOST']

    def test_run_task_success(self):
        """Test a successful run of a predefined task."""
        task_name = "generate_image"
        task_params = {"prompt": "a futuristic car"}
        expected_result = {"prompt_id": "12345"}

        self.mock_registry_instance.execute.return_value = expected_result

        result = asyncio.run(self.agent.run_task(task=task_name, params=task_params))

        self.mock_registry_instance.execute.assert_called_once_with(
            "sd.txt2img", json=task_params
        )
        self.assertEqual(result['status'], 'ok')
        self.assertIn(expected_result, result['artifacts'])

    def test_run_task_tool_not_found(self):
        """Test running a task where the tool does not exist."""
        self.mock_registry_instance.execute.side_effect = KeyError("Tool 'sd.txt2img' not found.")

        result = asyncio.run(self.agent.run_task(task="generate_image", params={}))

        self.assertEqual(result['status'], 'error')
        self.assertIn("Tool 'sd.txt2img' not found", result['message'])

    def test_run_task_external_tool_error(self):
        """Test running a task where the tool execution fails."""
        self.mock_registry_instance.execute.side_effect = ExternalToolError("ComfyUI is offline.")

        result = asyncio.run(self.agent.run_task(task="generate_image", params={}))

        self.assertEqual(result['status'], 'error')
        self.assertIn("ComfyUI is offline", result['message'])

    def test_run_unimplemented_task(self):
        """Test running a task that is not implemented in the agent's run_task method."""
        result = asyncio.run(self.agent.run_task(task="unimplemented_task", params={}))

        self.assertEqual(result['status'], 'error')
        self.assertIn("Predefined task 'unimplemented_task' is not implemented", result['message'])

if __name__ == '__main__':
    unittest.main()
