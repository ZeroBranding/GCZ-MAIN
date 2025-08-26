"""Core LangGraph implementation with persistent checkpointing."""
import asyncio
import json
import sqlite3
from pathlib import Path
from typing import TypedDict, Annotated, List, Dict, Any, Optional, Callable
from datetime import datetime
import uuid
from dataclasses import dataclass, field
import os

from core.logging import logger

# State definition
class GraphState(TypedDict):
    """State schema for the workflow graph."""
    session_id: str
    goal: str
    user_context: Dict[str, Any]
    plan: Optional[List[str]]
    current_step: int
    execution_results: List[Dict[str, Any]]
    artifacts: List[str]
    status: str  # planning, executing, completed, failed
    error: Optional[str]
    timestamp: str

# Custom implementation to replace LangGraph dependencies
@dataclass
class Checkpoint:
    """Checkpoint data structure."""
    v: int = 1
    id: str = ""
    ts: str = ""
    channel_values: Dict = field(default_factory=dict)
    channel_versions: Dict = field(default_factory=dict)
    versions_seen: Dict = field(default_factory=dict)
    pending_sends: List = field(default_factory=list)

class BaseCheckpointSaver:
    """Base class for checkpoint savers."""
    async def aget(self, config: Dict) -> Optional[Checkpoint]:
        return self.get(config)
    
    def get(self, config: Dict) -> Optional[Checkpoint]:
        raise NotImplementedError
        
    async def aput(self, config: Dict, checkpoint: Checkpoint, metadata: Dict) -> Dict:
        return self.put(config, checkpoint, metadata)
        
    def put(self, config: Dict, checkpoint: Checkpoint, metadata: Dict) -> Dict:
        raise NotImplementedError
        
    async def alist(self, config: Dict, *, filter: Optional[Dict] = None, before: Optional[Dict] = None, limit: int = 10) -> List[tuple]:
        return self.list(config, filter=filter, before=before, limit=limit)
        
    def list(self, config: Dict, *, filter: Optional[Dict] = None, before: Optional[Dict] = None, limit: int = 10) -> List[tuple]:
        raise NotImplementedError

class PersistentCheckpointer(BaseCheckpointSaver):
    """Custom checkpointer that uses SQLite + JSON for persistence."""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Use workspace-relative path instead of absolute /data
            workspace_path = os.environ.get("WORKSPACE_PATH", "/workspace")
            db_path = os.path.join(workspace_path, "data", "graph", "checkpoints.db")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
    def _init_db(self):
        """Initialize the SQLite database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT,
                    checkpoint_id TEXT,
                    parent_id TEXT,
                    checkpoint BLOB,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (thread_id, checkpoint_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_thread_created 
                ON checkpoints(thread_id, created_at DESC)
            """)
            
    def get(self, config: Dict) -> Optional[Checkpoint]:
        """Get the latest checkpoint for a thread."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None
            
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                """SELECT checkpoint, checkpoint_id, parent_id, metadata 
                   FROM checkpoints 
                   WHERE thread_id = ? 
                   ORDER BY created_at DESC 
                   LIMIT 1""",
                (thread_id,)
            )
            row = cursor.fetchone()
            
        if row:
            checkpoint_data = json.loads(row[0])
            return Checkpoint(
                v=1,
                id=row[1],
                ts=checkpoint_data.get("ts", datetime.now().isoformat()),
                channel_values=checkpoint_data.get("channel_values", {}),
                channel_versions=checkpoint_data.get("channel_versions", {}),
                versions_seen=checkpoint_data.get("versions_seen", {}),
                pending_sends=checkpoint_data.get("pending_sends", []),
            )
        return None
        
    def put(self, config: Dict, checkpoint: Checkpoint, metadata: Dict) -> Dict:
        """Save a checkpoint."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            thread_id = str(uuid.uuid4())
            
        checkpoint_id = checkpoint.id or str(uuid.uuid4())
        
        # Serialize checkpoint
        checkpoint_data = {
            "ts": checkpoint.ts or datetime.now().isoformat(),
            "channel_values": checkpoint.channel_values,
            "channel_versions": checkpoint.channel_versions,
            "versions_seen": checkpoint.versions_seen,
            "pending_sends": checkpoint.pending_sends,
        }
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO checkpoints 
                   (thread_id, checkpoint_id, parent_id, checkpoint, metadata) 
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    thread_id,
                    checkpoint_id,
                    metadata.get("parent_id"),
                    json.dumps(checkpoint_data),
                    json.dumps(metadata)
                )
            )
            
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id
            }
        }
        
    def list(self, config: Dict, *, filter: Optional[Dict] = None, before: Optional[Dict] = None, limit: int = 10) -> List[tuple]:
        """List checkpoints for a thread."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return []
            
        query = "SELECT checkpoint_id, parent_id, metadata, created_at FROM checkpoints WHERE thread_id = ?"
        params = [thread_id]
        
        if before:
            before_id = before.get("configurable", {}).get("checkpoint_id")
            if before_id:
                query += " AND created_at < (SELECT created_at FROM checkpoints WHERE checkpoint_id = ?)"
                params.append(before_id)
                
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(query, params)
            results = []
            for row in cursor:
                metadata = json.loads(row[2]) if row[2] else {}
                results.append((
                    {"configurable": {"thread_id": thread_id, "checkpoint_id": row[0]}},
                    metadata,
                    {"parent_id": row[1], "created_at": row[3]}
                ))
                
        return results

# Simple StateGraph implementation
END = "END"

class StateGraph:
    """Simple state graph implementation."""
    
    def __init__(self, state_type: type):
        self.state_type = state_type
        self.nodes: Dict[str, Callable] = {}
        self.edges: Dict[str, List[str]] = {}
        self.conditional_edges: Dict[str, tuple] = {}
        self.entry_point = None
        self.checkpointer = None
        
    def add_node(self, name: str, func: Callable):
        """Add a node to the graph."""
        self.nodes[name] = func
        
    def add_edge(self, from_node: str, to_node: str):
        """Add an edge between nodes."""
        if from_node not in self.edges:
            self.edges[from_node] = []
        self.edges[from_node].append(to_node)
        
    def add_conditional_edges(self, from_node: str, condition_func: Callable, routes: Dict[str, str]):
        """Add conditional edges."""
        self.conditional_edges[from_node] = (condition_func, routes)
        
    def set_entry_point(self, node: str):
        """Set the entry point of the graph."""
        self.entry_point = node
        
    def compile(self, checkpointer=None):
        """Compile the graph."""
        self.checkpointer = checkpointer
        return self
        
    async def ainvoke(self, initial_state: GraphState, config: Dict) -> GraphState:
        """Execute the graph asynchronously."""
        state = initial_state.copy() if initial_state else {}
        current_node = self.entry_point
        
        # Load checkpoint if available
        if self.checkpointer and config:
            checkpoint = await self.checkpointer.aget(config)
            if checkpoint and checkpoint.channel_values.get("state"):
                state = checkpoint.channel_values["state"]
                current_node = checkpoint.channel_values.get("next_node", current_node)
                
        visited = set()
        
        while current_node and current_node != END:
            if current_node in visited:
                # Prevent infinite loops
                if state.get("current_step", 0) >= len(state.get("plan", [])):
                    break
                    
            visited.add(current_node)
            
            # Execute node
            if current_node in self.nodes:
                logger.info(f"Executing node: {current_node}")
                node_func = self.nodes[current_node]
                state = await node_func(state)
                
                # Save checkpoint
                if self.checkpointer and config:
                    checkpoint = Checkpoint(
                        id=str(uuid.uuid4()),
                        ts=datetime.now().isoformat(),
                        channel_values={"state": state, "next_node": current_node}
                    )
                    await self.checkpointer.aput(config, checkpoint, {"node": current_node})
                    
            # Determine next node
            if current_node in self.conditional_edges:
                condition_func, routes = self.conditional_edges[current_node]
                next_key = condition_func(state)
                current_node = routes.get(next_key, END)
            elif current_node in self.edges:
                current_node = self.edges[current_node][0] if self.edges[current_node] else END
            else:
                current_node = END
                
        return state
        
    async def aget_state(self, config: Dict) -> Optional[Dict]:
        """Get the current state from checkpoint."""
        if self.checkpointer:
            checkpoint = await self.checkpointer.aget(config)
            if checkpoint:
                return {"values": checkpoint.channel_values.get("state", {})}
        return None

# Node implementations
async def plan_node(state: GraphState) -> GraphState:
    """Create execution plan based on goal."""
    logger.info(f"Planning for goal: {state['goal']}")
    
    # Simple planning logic - in production, use LLM
    if "image" in state["goal"].lower() or "bild" in state["goal"].lower():
        plan = ["generate_image", "upscale_image", "save_artifact"]
    else:
        plan = ["analyze_request", "execute_task", "generate_response"]
        
    state["plan"] = plan
    state["current_step"] = 0
    state["status"] = "executing"
    
    return state

async def execute_node(state: GraphState) -> GraphState:
    """Execute current step in the plan."""
    if not state.get("plan") or state["current_step"] >= len(state["plan"]):
        state["status"] = "completed"
        return state
        
    current_step = state["plan"][state["current_step"]]
    logger.info(f"Executing step {state['current_step']}: {current_step}")
    
    # Import executor here to avoid circular dependency
    from ai.graph.nodes.executor import execute_workflow_step
    
    try:
        result = await execute_workflow_step(
            step_name=current_step,
            session_id=state["session_id"],
            context=state["user_context"],
            previous_results=state.get("execution_results", [])
        )
        
        if "execution_results" not in state:
            state["execution_results"] = []
        state["execution_results"].append(result)
        
        # Extract artifacts
        if result.get("artifact_path"):
            if "artifacts" not in state:
                state["artifacts"] = []
            state["artifacts"].append(result["artifact_path"])
            
        state["current_step"] += 1
        
        # Check if we're done with all steps
        if state["current_step"] >= len(state["plan"]):
            state["status"] = "completed"
        
    except Exception as e:
        logger.error(f"Step execution failed: {e}")
        state["status"] = "failed"
        state["error"] = str(e)
        
    return state

async def report_node(state: GraphState) -> GraphState:
    """Generate final report of execution."""
    logger.info("Generating execution report")
    
    report = {
        "session_id": state["session_id"],
        "goal": state["goal"],
        "status": state["status"],
        "steps_completed": state.get("current_step", 0),
        "total_steps": len(state.get("plan", [])),
        "artifacts": state.get("artifacts", []),
        "timestamp": datetime.now().isoformat()
    }
    
    if state.get("error"):
        report["error"] = state["error"]
        
    # Save report - use workspace-relative path
    workspace_path = os.environ.get("WORKSPACE_PATH", "/workspace")
    report_path = Path(workspace_path) / "data" / "graph" / "reports" / f"{state['session_id']}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
        
    logger.info(f"Report saved to {report_path}")
    
    return state

def should_continue(state: GraphState) -> str:
    """Determine next step in the graph."""
    if state["status"] == "failed":
        return "report"
    elif state["status"] == "completed":
        return "report"
    elif state.get("current_step", 0) < len(state.get("plan", [])):
        return "execute"
    else:
        return "report"

def create_graph() -> StateGraph:
    """Create the main workflow graph."""
    # Initialize checkpointer
    checkpointer = PersistentCheckpointer()
    
    # Create graph
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("plan", plan_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("report", report_node)
    
    # Add edges
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "execute")
    workflow.add_conditional_edges(
        "execute",
        should_continue,
        {
            "execute": "execute",
            "report": "report"
        }
    )
    workflow.add_edge("report", END)
    
    # Compile with checkpointer
    app = workflow.compile(checkpointer=checkpointer)
    
    return app

# Global graph instance
_graph = None

def get_graph() -> StateGraph:
    """Get or create the global graph instance."""
    global _graph
    if _graph is None:
        _graph = create_graph()
    return _graph