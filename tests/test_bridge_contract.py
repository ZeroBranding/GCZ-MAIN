"""Contract tests for Graph-Engine Bridge.

Tests the contract between LangGraph tool calls and Workflow Engine,
ensuring proper translation and idempotent execution.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List
import json
import hashlib

from ai.graph.bridge import (
    GraphEngineBridge,
    StepSpec,
    WorkflowSpec,
    tool_call_to_workflow,
    get_bridge
)
from ai.adapters.providers import ToolCall
from ai.tools.bindings import ToolResult, ArtifactResult
from core.workflow_engine import WorkflowEngine


# Fixtures
@pytest.fixture
def mock_engine():
    """Mock workflow engine."""
    engine = Mock(spec=WorkflowEngine)
    engine.submit = AsyncMock()
    return engine


@pytest.fixture
def bridge(mock_engine):
    """Create bridge with mocked engine."""
    return GraphEngineBridge(engine=mock_engine)


@pytest.fixture
def sample_tool_calls():
    """Sample tool calls for testing."""
    return {
        "sd_generate": ToolCall(
            id="test_1",
            name="sd_generate",
            arguments={
                "prompt": "A beautiful sunset",
                "width": 512,
                "height": 512,
                "steps": 20,
                "seed": 42
            }
        ),
        "upscale": ToolCall(
            id="test_2",
            name="upscale_image",
            arguments={
                "image_path": "/path/to/image.png",
                "scale": 2,
                "model": "esrgan"
            }
        ),
        "animation": ToolCall(
            id="test_3",
            name="generate_animation",
            arguments={
                "prompt": "A dancing robot",
                "duration": 3.0,
                "style": "cartoon"
            }
        ),
        "asr": ToolCall(
            id="test_4",
            name="transcribe_audio",
            arguments={
                "audio_path": "/path/to/audio.wav",
                "language": "en",
                "format": "segments"
            }
        ),
        "tts": ToolCall(
            id="test_5",
            name="synthesize_speech",
            arguments={
                "text": "Hello world",
                "voice_profile": "emma",
                "backend": "openvoice"
            }
        ),
        "upload": ToolCall(
            id="test_6",
            name="upload_file",
            arguments={
                "file_path": "/path/to/file.txt",
                "destination": "local"
            }
        )
    }


# Test StepSpec
class TestStepSpec:
    """Test StepSpec data structure."""
    
    def test_step_spec_creation(self):
        """Test creating a StepSpec."""
        step = StepSpec(
            name="test_step",
            type="test_type",
            params={"param1": "value1"},
            depends_on=["prev_step"],
            outputs={"output1": "result"}
        )
        
        assert step.name == "test_step"
        assert step.type == "test_type"
        assert step.params["param1"] == "value1"
        assert "prev_step" in step.depends_on
        assert step.outputs["output1"] == "result"
        
    def test_step_spec_to_dict(self):
        """Test StepSpec conversion to dict."""
        step = StepSpec(
            name="test_step",
            type="test_type",
            params={"param1": "value1"}
        )
        
        step_dict = step.to_dict()
        
        assert step_dict["name"] == "test_step"
        assert step_dict["type"] == "test_type"
        assert step_dict["params"]["param1"] == "value1"
        assert "depends_on" not in step_dict  # Optional field
        
    def test_step_spec_with_dependencies(self):
        """Test StepSpec with dependencies."""
        step = StepSpec(
            name="dependent_step",
            type="process",
            params={},
            depends_on=["step1", "step2"]
        )
        
        step_dict = step.to_dict()
        assert step_dict["depends_on"] == ["step1", "step2"]


# Test WorkflowSpec
class TestWorkflowSpec:
    """Test WorkflowSpec data structure."""
    
    def test_workflow_spec_creation(self):
        """Test creating a WorkflowSpec."""
        steps = [
            StepSpec("step1", "type1", {}),
            StepSpec("step2", "type2", {}, depends_on=["step1"])
        ]
        
        workflow = WorkflowSpec(
            name="test_workflow",
            steps=steps,
            context={"user": "test"}
        )
        
        assert workflow.name == "test_workflow"
        assert len(workflow.steps) == 2
        assert workflow.context["user"] == "test"
        
    def test_workflow_spec_to_dict(self):
        """Test WorkflowSpec conversion to dict."""
        steps = [
            StepSpec("step1", "type1", {"param": "value"})
        ]
        
        workflow = WorkflowSpec("test", steps)
        workflow_dict = workflow.to_dict()
        
        assert workflow_dict["name"] == "test"
        assert len(workflow_dict["steps"]) == 1
        assert workflow_dict["steps"][0]["name"] == "step1"
        assert workflow_dict["steps"][0]["params"]["param"] == "value"
        
    def test_workflow_spec_to_yaml(self):
        """Test WorkflowSpec conversion to YAML."""
        steps = [
            StepSpec("step1", "type1", {"param": "value"})
        ]
        
        workflow = WorkflowSpec("test", steps)
        yaml_str = workflow.to_yaml()
        
        assert "name: test" in yaml_str
        assert "step1" in yaml_str
        assert "param: value" in yaml_str


# Test Tool Call to Steps Conversion
class TestToolCallToSteps:
    """Test conversion of tool calls to workflow steps."""
    
    def test_sd_generate_to_steps(self, bridge, sample_tool_calls):
        """Test SD generation tool call conversion."""
        tool_call = sample_tool_calls["sd_generate"]
        steps = bridge.tool_call_to_steps(tool_call)
        
        assert len(steps) >= 1  # At least generate step
        
        # Check generate step
        generate_step = next(s for s in steps if s.name == "generate_image")
        assert generate_step.type == "txt2img"
        assert generate_step.params["prompt"] == "A beautiful sunset"
        assert generate_step.params["width"] == 512
        assert generate_step.params["height"] == 512
        assert generate_step.params["steps"] == 20
        assert generate_step.params["seed"] == 42
        
        # Check save artifact step if present
        save_steps = [s for s in steps if s.name == "save_artifact"]
        if save_steps:
            save_step = save_steps[0]
            assert "generate_image" in save_step.depends_on
            
    def test_upscale_to_steps(self, bridge, sample_tool_calls):
        """Test upscale tool call conversion."""
        tool_call = sample_tool_calls["upscale"]
        steps = bridge.tool_call_to_steps(tool_call)
        
        assert len(steps) >= 2  # Load, upscale, save
        
        # Check load step
        load_step = next(s for s in steps if s.name == "load_image")
        assert load_step.type == "load_image"
        assert load_step.params["path"] == "/path/to/image.png"
        
        # Check upscale step
        upscale_step = next(s for s in steps if s.name == "upscale_image")
        assert upscale_step.type == "upscale"
        assert upscale_step.params["scale"] == 2
        assert upscale_step.params["model"] == "esrgan"
        assert "load_image" in upscale_step.depends_on
        
    def test_animation_to_steps(self, bridge, sample_tool_calls):
        """Test animation tool call conversion."""
        tool_call = sample_tool_calls["animation"]
        steps = bridge.tool_call_to_steps(tool_call)
        
        assert len(steps) == 3  # Keyframes, interpolate, render
        
        # Check steps are in order
        step_names = [s.name for s in steps]
        assert "generate_keyframes" in step_names
        assert "interpolate_frames" in step_names
        assert "render_animation" in step_names
        
        # Check dependencies
        interpolate_step = next(s for s in steps if s.name == "interpolate_frames")
        assert "generate_keyframes" in interpolate_step.depends_on
        
        render_step = next(s for s in steps if s.name == "render_animation")
        assert "interpolate_frames" in render_step.depends_on
        
    def test_asr_to_steps_with_segments(self, bridge, sample_tool_calls):
        """Test ASR tool call conversion with segments format."""
        tool_call = sample_tool_calls["asr"]
        steps = bridge.tool_call_to_steps(tool_call)
        
        # Should have format_segments step since format is "segments"
        format_steps = [s for s in steps if s.name == "format_segments"]
        assert len(format_steps) == 1
        assert "transcribe_audio" in format_steps[0].depends_on
        
    def test_tts_to_steps(self, bridge, sample_tool_calls):
        """Test TTS tool call conversion."""
        tool_call = sample_tool_calls["tts"]
        steps = bridge.tool_call_to_steps(tool_call)
        
        assert len(steps) == 3  # Prepare, synthesize, save
        
        # Check text preparation
        prepare_step = next(s for s in steps if s.name == "prepare_text")
        assert prepare_step.params["text"] == "Hello world"
        
        # Check synthesis
        synth_step = next(s for s in steps if s.name == "synthesize_speech")
        assert synth_step.params["voice"] == "emma"
        assert synth_step.params["backend"] == "openvoice"
        assert "prepare_text" in synth_step.depends_on
        
    def test_upload_local_to_steps(self, bridge, sample_tool_calls):
        """Test local upload tool call conversion."""
        tool_call = sample_tool_calls["upload"]
        steps = bridge.tool_call_to_steps(tool_call)
        
        assert len(steps) == 1
        assert steps[0].name == "upload_local"
        assert steps[0].type == "local_upload"
        assert steps[0].params["file_path"] == "/path/to/file.txt"
        
    def test_upload_telegram_to_steps(self, bridge):
        """Test telegram upload tool call conversion."""
        tool_call = ToolCall(
            id="test_telegram",
            name="upload_file",
            arguments={
                "file_path": "/path/to/file.txt",
                "destination": "telegram",
                "chat_id": "123456",
                "caption": "Test file"
            }
        )
        
        steps = bridge.tool_call_to_steps(tool_call)
        
        assert len(steps) == 1
        assert steps[0].name == "upload_telegram"
        assert steps[0].type == "telegram_upload"
        assert steps[0].params["chat_id"] == "123456"
        assert steps[0].params["caption"] == "Test file"
        
    def test_unknown_tool_to_steps(self, bridge):
        """Test unknown tool call conversion."""
        tool_call = ToolCall(
            id="test_unknown",
            name="unknown_tool",
            arguments={"param": "value"}
        )
        
        steps = bridge.tool_call_to_steps(tool_call)
        
        assert len(steps) == 1
        assert steps[0].name == "unknown_tool_step"
        assert steps[0].type == "unknown_tool"
        assert steps[0].params["param"] == "value"
        
    def test_deterministic_step_ordering(self, bridge, sample_tool_calls):
        """Test that steps are returned in deterministic order."""
        tool_call = sample_tool_calls["animation"]
        
        # Convert multiple times
        results = []
        for _ in range(5):
            steps = bridge.tool_call_to_steps(tool_call)
            step_names = [s.name for s in steps]
            results.append(step_names)
            
        # All results should be identical
        for result in results[1:]:
            assert result == results[0], "Step order should be deterministic"


# Test Submit and Wait
class TestSubmitAndWait:
    """Test workflow submission and waiting."""
    
    @pytest.mark.asyncio
    async def test_submit_workflow_spec(self, bridge, mock_engine):
        """Test submitting a WorkflowSpec."""
        steps = [
            StepSpec("step1", "type1", {"param": "value"})
        ]
        workflow = WorkflowSpec("test", steps)
        
        mock_engine.submit.return_value = {
            "status": "completed",
            "outputs": {"step1": {"result": "success"}}
        }
        
        result = await bridge.submit_and_wait(workflow)
        
        assert result.success == True
        assert result.data["step1"]["result"] == "success"
        
        # Check engine was called
        mock_engine.submit.assert_called_once()
        call_args = mock_engine.submit.call_args
        assert call_args[1]["workflow"]["name"] == "test"
        
    @pytest.mark.asyncio
    async def test_submit_step_list(self, bridge, mock_engine):
        """Test submitting a list of StepSpecs."""
        steps = [
            StepSpec("step1", "type1", {"param": "value"}),
            StepSpec("step2", "type2", {}, depends_on=["step1"])
        ]
        
        mock_engine.submit.return_value = {
            "status": "completed",
            "outputs": {}
        }
        
        result = await bridge.submit_and_wait(steps)
        
        assert result.success == True
        
        # Check workflow was constructed
        call_args = mock_engine.submit.call_args
        workflow = call_args[1]["workflow"]
        assert workflow["name"] == "tool_workflow"
        assert len(workflow["steps"]) == 2
        
    @pytest.mark.asyncio
    async def test_submit_with_correlation_id(self, bridge, mock_engine):
        """Test submission with correlation ID for idempotency."""
        steps = [StepSpec("step1", "type1", {})]
        correlation_id = "test_correlation_123"
        
        mock_engine.submit.return_value = {
            "status": "completed",
            "outputs": {}
        }
        
        result = await bridge.submit_and_wait(steps, correlation_id=correlation_id)
        
        assert result.success == True
        assert result.metadata["correlation_id"] == correlation_id
        
        # Check engine was called with correlation ID
        call_args = mock_engine.submit.call_args
        assert call_args[1]["correlation_id"] == correlation_id
        
    @pytest.mark.asyncio
    async def test_submit_generates_correlation_id(self, bridge, mock_engine):
        """Test that correlation ID is generated if not provided."""
        steps = [StepSpec("step1", "type1", {"param": "value"})]
        
        mock_engine.submit.return_value = {
            "status": "completed",
            "outputs": {}
        }
        
        result = await bridge.submit_and_wait(steps)
        
        # Check correlation ID was generated
        call_args = mock_engine.submit.call_args
        correlation_id = call_args[1]["correlation_id"]
        assert correlation_id is not None
        assert len(correlation_id) == 32  # MD5 hex digest length
        
        # Same spec should generate same ID (deterministic)
        mock_engine.reset_mock()
        result2 = await bridge.submit_and_wait(steps)
        call_args2 = mock_engine.submit.call_args
        correlation_id2 = call_args2[1]["correlation_id"]
        assert correlation_id == correlation_id2
        
    @pytest.mark.asyncio
    async def test_submit_with_artifact_result(self, bridge, mock_engine):
        """Test submission that returns an artifact."""
        steps = [StepSpec("generate", "txt2img", {})]
        
        mock_engine.submit.return_value = {
            "status": "completed",
            "outputs": {
                "generate": {
                    "image_path": "/artifacts/image.png"
                }
            }
        }
        
        result = await bridge.submit_and_wait(steps)
        
        assert isinstance(result, ArtifactResult)
        assert result.success == True
        assert result.artifact_path == "/artifacts/image.png"
        assert result.artifact_type == "image/png"
        
    @pytest.mark.asyncio
    async def test_submit_with_video_artifact(self, bridge, mock_engine):
        """Test submission that returns a video artifact."""
        steps = [StepSpec("render", "render_video", {})]
        
        mock_engine.submit.return_value = {
            "status": "completed",
            "outputs": {
                "render": {
                    "video_path": "/artifacts/video.mp4"
                }
            }
        }
        
        result = await bridge.submit_and_wait(steps)
        
        assert isinstance(result, ArtifactResult)
        assert result.artifact_path == "/artifacts/video.mp4"
        assert result.artifact_type == "video/mp4"
        
    @pytest.mark.asyncio
    async def test_submit_with_audio_artifact(self, bridge, mock_engine):
        """Test submission that returns an audio artifact."""
        steps = [StepSpec("synthesize", "tts", {})]
        
        mock_engine.submit.return_value = {
            "status": "completed",
            "outputs": {
                "synthesize": {
                    "audio_path": "/artifacts/audio.wav"
                }
            }
        }
        
        result = await bridge.submit_and_wait(steps)
        
        assert isinstance(result, ArtifactResult)
        assert result.artifact_path == "/artifacts/audio.wav"
        assert result.artifact_type == "audio/wav"
        
    @pytest.mark.asyncio
    async def test_submit_failure(self, bridge, mock_engine):
        """Test handling of workflow execution failure."""
        steps = [StepSpec("step1", "type1", {})]
        
        mock_engine.submit.return_value = {
            "status": "failed",
            "error": "Step execution failed"
        }
        
        result = await bridge.submit_and_wait(steps)
        
        assert result.success == False
        assert result.error == "Step execution failed"
        assert result.metadata["status"] == "failed"
        
    @pytest.mark.asyncio
    async def test_submit_timeout(self, bridge, mock_engine):
        """Test handling of submission timeout."""
        steps = [StepSpec("step1", "type1", {})]
        
        # Make submit take too long
        async def slow_submit(*args, **kwargs):
            await asyncio.sleep(5)
            return {"status": "completed"}
            
        mock_engine.submit = slow_submit
        
        result = await bridge.submit_and_wait(steps, timeout=0.1)
        
        assert result.success == False
        assert "timed out" in result.error
        
    @pytest.mark.asyncio
    async def test_submit_exception(self, bridge, mock_engine):
        """Test handling of submission exception."""
        steps = [StepSpec("step1", "type1", {})]
        
        mock_engine.submit.side_effect = Exception("Engine error")
        
        result = await bridge.submit_and_wait(steps)
        
        assert result.success == False
        assert "Engine error" in result.error


# Test Idempotency
class TestIdempotency:
    """Test idempotent execution via correlation ID."""
    
    @pytest.mark.asyncio
    async def test_same_tool_call_same_correlation_id(self, bridge, mock_engine):
        """Test that same tool call generates same correlation ID."""
        tool_call = ToolCall(
            id="test",
            name="sd_generate",
            arguments={"prompt": "test", "width": 512}
        )
        
        mock_engine.submit.return_value = {
            "status": "completed",
            "outputs": {}
        }
        
        # Convert to steps twice
        steps1 = bridge.tool_call_to_steps(tool_call)
        steps2 = bridge.tool_call_to_steps(tool_call)
        
        # Submit both
        await bridge.submit_and_wait(steps1)
        await bridge.submit_and_wait(steps2)
        
        # Get correlation IDs from calls
        calls = mock_engine.submit.call_args_list
        assert len(calls) == 2
        
        correlation_id1 = calls[0][1]["correlation_id"]
        correlation_id2 = calls[1][1]["correlation_id"]
        
        # Should be the same due to deterministic generation
        assert correlation_id1 == correlation_id2
        
    @pytest.mark.asyncio
    async def test_explicit_correlation_id_preserved(self, bridge, mock_engine):
        """Test that explicit correlation ID is preserved."""
        steps = [StepSpec("step1", "type1", {})]
        correlation_id = "explicit_id_123"
        
        mock_engine.submit.return_value = {
            "status": "completed",
            "outputs": {}
        }
        
        # Submit multiple times with same ID
        for _ in range(3):
            result = await bridge.submit_and_wait(steps, correlation_id=correlation_id)
            assert result.metadata["correlation_id"] == correlation_id
            
        # All calls should have the same correlation ID
        calls = mock_engine.submit.call_args_list
        for call in calls:
            assert call[1]["correlation_id"] == correlation_id


# Test Global Functions
class TestGlobalFunctions:
    """Test global convenience functions."""
    
    def test_get_bridge_singleton(self):
        """Test that get_bridge returns singleton."""
        bridge1 = get_bridge()
        bridge2 = get_bridge()
        
        assert bridge1 is bridge2
        
    @pytest.mark.asyncio
    async def test_tool_call_to_workflow(self):
        """Test the tool_call_to_workflow convenience function."""
        tool_call = ToolCall(
            id="test",
            name="sd_generate",
            arguments={"prompt": "test"}
        )
        
        with patch("ai.graph.bridge.get_bridge") as mock_get_bridge:
            mock_bridge = Mock()
            mock_bridge.tool_call_to_steps.return_value = [
                StepSpec("step1", "type1", {})
            ]
            mock_bridge.submit_and_wait = AsyncMock(return_value=ToolResult(
                success=True,
                data={"result": "success"}
            ))
            mock_get_bridge.return_value = mock_bridge
            
            result = await tool_call_to_workflow(tool_call)
            
            assert result.success == True
            assert result.data["result"] == "success"
            
            # Check correlation ID format
            mock_bridge.submit_and_wait.assert_called_once()
            call_args = mock_bridge.submit_and_wait.call_args
            correlation_id = call_args[1]["correlation_id"]
            assert correlation_id == f"{tool_call.id}:{tool_call.name}"


# Test Error Paths
class TestErrorPaths:
    """Test error handling paths."""
    
    @pytest.mark.asyncio
    async def test_invalid_step_spec(self, bridge, mock_engine):
        """Test handling of invalid step specifications."""
        # Create step with None params (invalid)
        steps = [
            StepSpec("step1", "type1", None)  # This should be handled gracefully
        ]
        
        mock_engine.submit.return_value = {
            "status": "error",
            "error": "Invalid step parameters"
        }
        
        result = await bridge.submit_and_wait(steps)
        
        assert result.success == False
        assert "Invalid step parameters" in result.error
        
    @pytest.mark.asyncio
    async def test_engine_not_available(self):
        """Test handling when engine is not available."""
        # Create bridge without engine
        bridge = GraphEngineBridge(engine=None)
        
        # Should create default engine
        assert bridge.engine is not None
        assert isinstance(bridge.engine, WorkflowEngine)
        
    def test_empty_tool_call(self, bridge):
        """Test handling of empty tool call."""
        tool_call = ToolCall(
            id="empty",
            name="",
            arguments={}
        )
        
        steps = bridge.tool_call_to_steps(tool_call)
        
        # Should return default single step
        assert len(steps) == 1
        assert steps[0].name == "_step"
        assert steps[0].type == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])