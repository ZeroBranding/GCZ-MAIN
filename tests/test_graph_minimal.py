"""Minimal tests for LangGraph implementation with Mock-Engine."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json
import tempfile
import shutil

from ai.graph.core_graph import create_graph, GraphState, PersistentCheckpointer, Checkpoint
from ai.graph.run import start_graph, resume_graph, cancel_graph
from ai.graph.nodes.executor import execute_workflow_step

@pytest.fixture
def mock_workflow_engine():
    """Mock the workflow engine for testing."""
    with patch("core.workflow_engine.submit") as mock_submit:
        # Configure mock to return successful results
        async def mock_submit_impl(workflow, correlation_id=None, **kwargs):
            # Simulate different workflow types
            if isinstance(workflow, dict):
                workflow_name = workflow.get("name", "unknown")
                
                if "txt2img" in str(workflow):
                    return {
                        "status": "success",
                        "outputs": {
                            "txt2img": {
                                "image_path": f"/artifacts/test_image_{correlation_id}.png",
                                "prompt": kwargs.get("prompt", "test prompt")
                            }
                        }
                    }
                elif "upscale" in str(workflow):
                    return {
                        "status": "success",
                        "outputs": {
                            "upscale": {
                                "image_path": f"/artifacts/test_upscaled_{correlation_id}.png",
                                "scale": 2
                            }
                        }
                    }
                else:
                    return {
                        "status": "success",
                        "outputs": {
                            workflow_name: {"result": "executed"}
                        }
                    }
            return {"status": "success", "outputs": {}}
            
        mock_submit.side_effect = mock_submit_impl
        yield mock_submit

@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for testing."""
    temp_dir = tempfile.mkdtemp()
    data_path = Path(temp_dir) / "data" / "graph"
    data_path.mkdir(parents=True, exist_ok=True)
    
    # Set environment variable for workspace path
    import os
    old_workspace = os.environ.get("WORKSPACE_PATH")
    os.environ["WORKSPACE_PATH"] = temp_dir
    
    yield data_path
        
    # Cleanup
    if old_workspace:
        os.environ["WORKSPACE_PATH"] = old_workspace
    else:
        os.environ.pop("WORKSPACE_PATH", None)
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.mark.asyncio
async def test_plan_execute_report_flow(mock_workflow_engine, temp_data_dir):
    """Test the basic Plan→Execute→Report flow."""
    # Create graph
    graph = create_graph()
    
    # Initial state
    initial_state: GraphState = {
        "session_id": "test_session_1",
        "goal": "Generate an image of a sunset",
        "user_context": {"user_id": "test_user"},
        "plan": None,
        "current_step": 0,
        "execution_results": [],
        "artifacts": [],
        "status": "planning",
        "error": None,
        "timestamp": "2024-01-01T00:00:00"
    }
    
    # Run graph
    config = {"configurable": {"thread_id": "test_session_1"}}
    final_state = await graph.ainvoke(initial_state, config)
    
    # Assertions
    assert final_state["status"] == "completed"
    assert final_state["plan"] is not None
    assert len(final_state["plan"]) > 0
    assert final_state["current_step"] > 0
    assert len(final_state["execution_results"]) > 0
    
    # Check that artifacts were collected
    if "image" in initial_state["goal"].lower():
        assert len(final_state.get("artifacts", [])) > 0

@pytest.mark.asyncio
async def test_executor_idempotency(mock_workflow_engine):
    """Test that executor maintains idempotency."""
    correlation_id = "test_session:generate_image:0"
    context = {"prompt": "test prompt"}
    
    # First execution
    result1 = await execute_workflow_step(
        step_name="generate_image",
        session_id="test_session",
        context=context,
        previous_results=[]
    )
    
    # Second execution with same correlation ID
    result2 = await execute_workflow_step(
        step_name="generate_image",
        session_id="test_session",
        context=context,
        previous_results=[]
    )
    
    # Should return the same result (cached)
    assert result1 == result2
    
    # Mock should only be called once due to caching
    assert mock_workflow_engine.call_count == 1

@pytest.mark.asyncio
async def test_start_graph_integration(mock_workflow_engine, temp_data_dir):
    """Test the start_graph entry point."""
    result = await start_graph(
        session_id="test_integration",
        goal="Generate an image of a mountain",
        user_context={"source": "test"}
    )
    
    assert result["session_id"] == "test_integration"
    assert result["status"] in ["completed", "success"]
    assert "artifacts" in result
    assert "execution_results" in result

@pytest.mark.asyncio
async def test_graph_with_error_handling(mock_workflow_engine, temp_data_dir):
    """Test graph handles errors gracefully."""
    # Configure mock to fail
    async def mock_fail(*args, **kwargs):
        raise Exception("Simulated workflow failure")
        
    mock_workflow_engine.side_effect = mock_fail
    
    # Create graph
    graph = create_graph()
    
    initial_state: GraphState = {
        "session_id": "test_error",
        "goal": "Test error handling",
        "user_context": {},
        "plan": None,
        "current_step": 0,
        "execution_results": [],
        "artifacts": [],
        "status": "planning",
        "error": None,
        "timestamp": "2024-01-01T00:00:00"
    }
    
    config = {"configurable": {"thread_id": "test_error"}}
    final_state = await graph.ainvoke(initial_state, config)
    
    # Should complete with error status
    assert final_state["status"] == "failed"
    assert final_state["error"] is not None

@pytest.mark.asyncio
async def test_checkpoint_persistence(temp_data_dir):
    """Test that checkpoints are persisted correctly."""
    checkpointer = PersistentCheckpointer(str(temp_data_dir / "test_checkpoints.db"))
    
    # Create a checkpoint
    config = {"configurable": {"thread_id": "test_thread"}}
    
    checkpoint = Checkpoint(
        v=1,
        id="checkpoint_1",
        ts="2024-01-01T00:00:00",
        channel_values={"test": "value"},
        channel_versions={},
        versions_seen={},
        pending_sends=[]
    )
    
    # Save checkpoint
    result = checkpointer.put(config, checkpoint, {"test": "metadata"})
    
    assert result["configurable"]["thread_id"] == "test_thread"
    assert "checkpoint_id" in result["configurable"]
    
    # Retrieve checkpoint
    retrieved = checkpointer.get(config)
    assert retrieved is not None
    assert retrieved.channel_values == {"test": "value"}
    
    # List checkpoints
    checkpoints = checkpointer.list(config)
    assert len(checkpoints) > 0

@pytest.mark.asyncio
async def test_resume_functionality(mock_workflow_engine, temp_data_dir):
    """Test resuming an interrupted graph execution."""
    # Start initial execution
    result1 = await start_graph(
        session_id="test_resume",
        goal="Multi-step task",
        user_context={"initial": True}
    )
    
    # Simulate resumption (would normally be after interruption)
    # Note: In real scenario, we'd interrupt mid-execution
    # For testing, we just verify the resume mechanism works
    result2 = await resume_graph(
        session_id="test_resume",
        additional_context={"resumed": True}
    )
    
    # Should handle resume attempt (even if already completed)
    assert result2["session_id"] == "test_resume"

@pytest.mark.asyncio
async def test_cancel_functionality():
    """Test cancelling a graph execution."""
    # Start execution
    result = await start_graph(
        session_id="test_cancel",
        goal="Task to cancel"
    )
    
    # Cancel it
    cancelled = await cancel_graph("test_cancel")
    assert cancelled == True
    
    # Try to cancel non-existent session
    not_cancelled = await cancel_graph("non_existent")
    assert not_cancelled == False

@pytest.mark.asyncio  
async def test_workflow_yaml_loading():
    """Test loading workflow from YAML file."""
    from ai.graph.nodes.executor import WorkflowExecutor
    
    executor = WorkflowExecutor()
    
    # Create a test workflow file
    test_workflow_dir = Path("flows")
    test_workflow_dir.mkdir(exist_ok=True)
    
    test_workflow_file = test_workflow_dir / "test_workflow.yml"
    test_workflow_file.write_text("""
name: test_workflow
steps:
  - name: step1
    type: test
    params:
      key: value
""")
    
    try:
        # Test loading workflow
        workflow = await executor._prepare_workflow(
            "test_workflow",
            {},
            None
        )
        
        assert workflow is not None
        assert workflow["name"] == "test_workflow"
        assert len(workflow["steps"]) == 1
        
    finally:
        # Cleanup
        test_workflow_file.unlink(missing_ok=True)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])