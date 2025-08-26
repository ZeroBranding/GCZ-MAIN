# AI Module - LangGraph Integration

## Quick Start

The AI module provides a simple entry point for LangGraph execution:

```python
from ai import start_graph

# Start a new graph execution
result = await start_graph(
    session_id="unique-session-id",  # Optional, will be generated if not provided
    goal="Generate an image of a cat",  # The task/goal to execute
    user_ctx={"user_id": "123"}  # Optional user context
)

# Result contains:
# - session_id: The execution session ID
# - status: "completed", "failed", or "cancelled"
# - artifacts: List of generated artifacts (images, texts, etc.)
# - execution_results: Detailed execution steps
```

## Main Components

- `ai.graph.run`: Graph execution engine
- `ai.graph.core_graph`: Core graph definition and state management
- `ai.graph.nodes`: Individual graph nodes for different tasks
- `ai.tools`: Tool definitions for LangGraph

## Integration with Telegram Bot

The telegram bot integrates with the graph via:
- `/img <prompt>`: Triggers image generation through the graph
- `/upscale <image>`: Triggers image upscaling through the graph

## Dependencies

- langgraph: Graph execution framework
- langchain: LLM orchestration
- langchain-community: Community integrations
- langchain-openai: OpenAI integration
- pydantic>=2: Data validation
- aiosqlite: Async SQLite for persistence