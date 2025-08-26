"""AI module for LangGraph and agent implementations."""

from ai.graph.run import start_graph, resume_graph, cancel_graph

__all__ = ["start_graph", "resume_graph", "cancel_graph"]

# Quick start entry point
async def quick_start(session_id: str = None, goal: str = "", user_ctx: dict = None):
    """
    Quick start function for graph execution.
    
    Args:
        session_id: Optional session ID (will be generated if not provided)
        goal: The goal/prompt for execution
        user_ctx: Additional user context
        
    Returns:
        Execution result with artifacts
    """
    return await start_graph(session_id, goal, user_ctx)