"""Run module - Entry point for LangGraph execution."""
import asyncio
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from ai.graph.core_graph import get_graph, GraphState
from ai.graph.tools import get_openai_tools, execute_tool
from core.logging import logger
from core.monitoring import GRAPH_SESSION_DURATION_MS

class GraphRunner:
    """Manages LangGraph execution sessions."""
    
    def __init__(self):
        self.graph = get_graph()
        self.sessions: Dict[str, Dict] = {}
        
    async def start_graph(
        self,
        session_id: Optional[str] = None,
        goal: str = "",
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Start a new graph execution session.
        
        Args:
            session_id: Optional session ID (will be generated if not provided)
            goal: The goal/prompt for the execution
            user_context: Additional user context
            
        Returns:
            Execution result with session info and artifacts
        """
        # Generate session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
            
        logger.info(f"Starting graph execution: session={session_id}, goal={goal[:50]}...")
        
        # Prepare initial state
        initial_state: GraphState = {
            "session_id": session_id,
            "goal": goal,
            "user_context": user_context or {},
            "plan": None,
            "current_step": 0,
            "execution_results": [],
            "artifacts": [],
            "status": "planning",
            "error": None,
            "timestamp": datetime.now().isoformat()
        }
        
        # Store session info
        start_time = datetime.now()
        self.sessions[session_id] = {
            "started_at": start_time,
            "goal": goal,
            "status": "running"
        }
        
        try:
            # Run the graph with checkpointing
            config = {
                "configurable": {
                    "thread_id": session_id
                }
            }
            
            # Execute graph
            final_state = await self.graph.ainvoke(initial_state, config)
            
            # Update session status
            completed_at = datetime.now()
            self.sessions[session_id]["status"] = final_state["status"]
            self.sessions[session_id]["completed_at"] = completed_at

            # Record session duration metric
            duration_ms = (completed_at - start_time).total_seconds() * 1000
            GRAPH_SESSION_DURATION_MS.observe(duration_ms)
            
            # Prepare result
            result = {
                "session_id": session_id,
                "status": final_state["status"],
                "artifacts": final_state.get("artifacts", []),
                "execution_results": final_state.get("execution_results", []),
                "error": final_state.get("error")
            }
            
            logger.info(f"Graph execution completed: session={session_id}, status={final_state['status']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Graph execution failed: {e}")
            self.sessions[session_id]["status"] = "failed"
            self.sessions[session_id]["error"] = str(e)
            
            return {
                "session_id": session_id,
                "status": "failed",
                "error": str(e),
                "artifacts": []
            }
            
    async def resume_graph(
        self,
        session_id: str,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resume a previously interrupted graph execution.
        
        Args:
            session_id: Session ID to resume
            additional_context: Additional context for resumption
            
        Returns:
            Execution result
        """
        logger.info(f"Resuming graph execution: session={session_id}")
        
        if session_id not in self.sessions:
            return {
                "session_id": session_id,
                "status": "error",
                "error": "Session not found"
            }
            
        try:
            # Get checkpoint config
            config = {
                "configurable": {
                    "thread_id": session_id
                }
            }
            
            # Get current state from checkpoint
            state = await self.graph.aget_state(config)
            
            if not state:
                return {
                    "session_id": session_id,
                    "status": "error",
                    "error": "No checkpoint found for session"
                }
                
            # Update context if provided
            if additional_context:
                state.values["user_context"].update(additional_context)
                
            # Resume execution
            final_state = await self.graph.ainvoke(None, config)
            
            # Update session
            self.sessions[session_id]["resumed_at"] = datetime.now()
            self.sessions[session_id]["status"] = final_state["status"]
            
            return {
                "session_id": session_id,
                "status": final_state["status"],
                "artifacts": final_state.get("artifacts", []),
                "execution_results": final_state.get("execution_results", [])
            }
            
        except Exception as e:
            logger.error(f"Graph resumption failed: {e}")
            return {
                "session_id": session_id,
                "status": "error",
                "error": str(e)
            }
            
    async def cancel_graph(self, session_id: str) -> bool:
        """
        Cancel a running graph execution.
        
        Args:
            session_id: Session ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        if session_id in self.sessions:
            self.sessions[session_id]["status"] = "cancelled"
            self.sessions[session_id]["cancelled_at"] = datetime.now()
            logger.info(f"Cancelled graph execution: session={session_id}")
            return True
        return False
        
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a session."""
        return self.sessions.get(session_id)
        
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        return [
            {"session_id": sid, **info}
            for sid, info in self.sessions.items()
        ]

# Global runner instance
_runner = GraphRunner()

async def start_graph(
    session_id: Optional[str] = None,
    goal: str = "",
    user_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Start a new graph execution.
    
    This is the main entry point for telegram_bot integration.
    
    Args:
        session_id: Optional session ID
        goal: The goal/prompt for execution
        user_context: Additional user context
        
    Returns:
        Execution result with artifacts
    """
    return await _runner.start_graph(session_id, goal, user_context)

async def resume_graph(
    session_id: str,
    additional_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Resume a previously interrupted graph execution."""
    return await _runner.resume_graph(session_id, additional_context)

async def cancel_graph(session_id: str) -> bool:
    """Cancel a running graph execution."""
    return await _runner.cancel_graph(session_id)

def get_session_info(session_id: str) -> Optional[Dict[str, Any]]:
    """Get information about a session."""
    return _runner.get_session_info(session_id)

def list_sessions() -> List[Dict[str, Any]]:
    """List all sessions."""
    return _runner.list_sessions()

# Integration helper for telegram_bot
async def process_telegram_command(
    command: str,
    args: List[str],
    user_id: str,
    chat_id: str
) -> Dict[str, Any]:
    """
    Process a telegram command through the graph.
    
    Args:
        command: The command (e.g., "img", "anim")
        args: Command arguments
        user_id: Telegram user ID
        chat_id: Telegram chat ID
        
    Returns:
        Result with artifacts for telegram response
    """
    # Prepare goal based on command
    if command == "img":
        goal = f"Generate image: {' '.join(args)}"
    elif command == "anim":
        goal = f"Generate animation: {' '.join(args)}"
    else:
        goal = ' '.join(args)
        
    # Prepare user context
    user_context = {
        "user_id": user_id,
        "chat_id": chat_id,
        "command": command,
        "prompt": ' '.join(args),
        "source": "telegram"
    }
    
    # Generate session ID based on user and timestamp
    session_id = f"telegram_{user_id}_{int(datetime.now().timestamp())}"
    
    # Start graph execution
    result = await start_graph(
        session_id=session_id,
        goal=goal,
        user_context=user_context
    )
    
    return result

# CLI interface for testing
async def main():
    """CLI interface for testing the graph."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m ai.graph.run <goal>")
        print("Example: python -m ai.graph.run 'Generate an image of a sunset'")
        sys.exit(1)
        
    goal = ' '.join(sys.argv[1:])
    
    print(f"Starting graph with goal: {goal}")
    result = await start_graph(goal=goal)
    
    print(f"\nExecution completed!")
    print(f"Status: {result['status']}")
    
    if result.get('artifacts'):
        print(f"Artifacts: {result['artifacts']}")
        
    if result.get('error'):
        print(f"Error: {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())