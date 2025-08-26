"""Integration tests for tool bindings to services."""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil
from datetime import datetime

from ai.tools import (
    ToolResult,
    ArtifactResult,
    ToolBindings,
    execute_tool_call,
    get_available_tools,
    SDGenerateParams,
    UpscaleParams,
    UploadParams,
    ASRParams,
    TTSParams,
    AnimationParams
)
from ai.adapters.providers import ToolCall
from ai.adapters.registry import get_registry


# Fixtures
@pytest.fixture
def temp_artifacts_dir():
    """Create temporary artifacts directory."""
    temp_dir = tempfile.mkdtemp()
    artifacts_dir = Path(temp_dir) / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    (artifacts_dir / "images").mkdir(exist_ok=True)
    (artifacts_dir / "uploads").mkdir(exist_ok=True)
    (artifacts_dir / "audio").mkdir(exist_ok=True)
    
    yield artifacts_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_sd_service():
    """Mock SDService."""
    with patch("services.sd_service.SDService") as MockSD:
        instance = MockSD.return_value
        instance.txt2img.return_value = "/artifacts/images/generated_image.png"
        instance.upscale.side_effect = NotImplementedError("Upscale not implemented")
        yield instance


@pytest.fixture
def mock_asr_service():
    """Mock ASRService."""
    with patch("services.asr_service.ASRService") as MockASR:
        instance = MockASR.return_value
        instance.transcribe_stream = AsyncMock(return_value=[
            {"text": "Hello", "start": 0.0, "end": 1.0},
            {"text": "world", "start": 1.0, "end": 2.0}
        ])
        yield instance


@pytest.fixture
def mock_voice_service():
    """Mock VoiceService."""
    with patch("services.voice_service.VoiceService") as MockVoice:
        instance = MockVoice.return_value
        instance.synthesize.return_value = "/artifacts/audio/synthesized.wav"
        yield instance


@pytest.fixture
def mock_anim_service():
    """Mock AnimService."""
    with patch("services.anim_service.AnimService") as MockAnim:
        instance = MockAnim.return_value
        instance.generate_animation = AsyncMock(
            return_value="/artifacts/animations/animation.mp4"
        )
        yield instance


@pytest.fixture
def tool_bindings():
    """Create ToolBindings instance."""
    return ToolBindings()


# Test parameter validation
class TestParameterValidation:
    """Test parameter validation for tool models."""
    
    def test_sd_generate_params(self):
        """Test SD generation parameter validation."""
        # Valid params
        params = SDGenerateParams(
            prompt="A beautiful landscape",
            width=512,
            height=512,
            steps=20
        )
        assert params.prompt == "A beautiful landscape"
        assert params.width == 512
        
        # Test constraints
        with pytest.raises(ValueError):
            SDGenerateParams(prompt="", width=10000)  # Width too large
            
    def test_upscale_params(self):
        """Test upscale parameter validation."""
        params = UpscaleParams(
            image_path="/path/to/image.png",
            scale=2
        )
        assert params.scale == 2
        
        # Test constraints
        with pytest.raises(ValueError):
            UpscaleParams(image_path="/path/to/image.png", scale=10)  # Scale too large
            
    def test_asr_params(self):
        """Test ASR parameter validation."""
        params = ASRParams(
            audio_path="/path/to/audio.wav",
            language="en",
            format="text"
        )
        assert params.language == "en"
        assert params.format == "text"
        
    def test_tts_params(self):
        """Test TTS parameter validation."""
        params = TTSParams(
            text="Hello world",
            voice_profile="default",
            backend="openvoice"
        )
        assert params.text == "Hello world"
        assert params.backend == "openvoice"


# Test tool registration
class TestToolRegistration:
    """Test tool schema registration."""
    
    def test_tools_registered(self, tool_bindings):
        """Test that all tools are registered."""
        registry = tool_bindings.registry
        
        # Check tools are registered
        assert registry.get("sd_generate") is not None
        assert registry.get("upscale_image") is not None
        assert registry.get("upload_file") is not None
        assert registry.get("transcribe_audio") is not None
        assert registry.get("synthesize_speech") is not None
        assert registry.get("generate_animation") is not None
        
    def test_tool_schemas(self, tool_bindings):
        """Test tool schemas are properly formatted."""
        registry = tool_bindings.registry
        
        # Check SD generate schema
        sd_schema = registry.get("sd_generate")
        assert sd_schema.name == "sd_generate"
        assert "prompt" in sd_schema.parameters["properties"]
        assert "width" in sd_schema.parameters["properties"]
        assert sd_schema.parameters["properties"]["width"]["minimum"] == 128
        assert sd_schema.parameters["properties"]["width"]["maximum"] == 2048
        
    def test_tool_tags(self, tool_bindings):
        """Test tools can be retrieved by tags."""
        registry = tool_bindings.registry
        
        # Get image-related tools
        image_tools = registry.get_by_tags(["image"])
        assert len(image_tools) >= 2  # sd_generate and upscale_image
        
        # Get audio-related tools
        audio_tools = registry.get_by_tags(["audio"])
        assert len(audio_tools) >= 2  # transcribe_audio and synthesize_speech


# Test SD service integration
class TestSDServiceIntegration:
    """Test SD service tool integration."""
    
    @pytest.mark.asyncio
    async def test_sd_generate_success(self, mock_sd_service, tool_bindings):
        """Test successful SD image generation."""
        tool_call = ToolCall(
            id="call_1",
            name="sd_generate",
            arguments={
                "prompt": "A beautiful sunset",
                "width": 512,
                "height": 512,
                "steps": 20
            }
        )
        
        result = await tool_bindings.execute_tool(tool_call)
        
        assert isinstance(result, ArtifactResult)
        assert result.success == True
        assert result.artifact_path == "/artifacts/images/generated_image.png"
        assert result.artifact_type == "image/png"
        assert result.data["prompt"] == "A beautiful sunset"
        
        # Verify service was called
        mock_sd_service.txt2img.assert_called_once_with(
            "A beautiful sunset",
            None,  # negative_prompt
            512,   # width
            512,   # height
            20,    # steps
            None   # seed
        )
        
    @pytest.mark.asyncio
    async def test_sd_generate_with_all_params(self, mock_sd_service, tool_bindings):
        """Test SD generation with all parameters."""
        tool_call = ToolCall(
            id="call_2",
            name="sd_generate",
            arguments={
                "prompt": "A mountain",
                "negative_prompt": "blurry",
                "width": 1024,
                "height": 768,
                "steps": 30,
                "seed": 42
            }
        )
        
        result = await tool_bindings.execute_tool(tool_call)
        
        assert result.success == True
        mock_sd_service.txt2img.assert_called_with(
            "A mountain",
            "blurry",
            1024,
            768,
            30,
            42
        )
        
    @pytest.mark.asyncio
    async def test_sd_generate_error(self, tool_bindings):
        """Test SD generation error handling."""
        with patch("services.sd_service.SDService") as MockSD:
            MockSD.return_value.txt2img.side_effect = Exception("ComfyUI error")
            
            tool_call = ToolCall(
                id="call_3",
                name="sd_generate",
                arguments={"prompt": "test"}
            )
            
            result = await tool_bindings.execute_tool(tool_call)
            
            assert result.success == False
            assert "ComfyUI error" in result.error
            assert result.metadata["service"] == "sd_service"


# Test upscale integration
class TestUpscaleIntegration:
    """Test upscale tool integration."""
    
    @pytest.mark.asyncio
    async def test_upscale_fallback(self, temp_artifacts_dir):
        """Test upscale with fallback implementation."""
        # Create a test image
        test_image = temp_artifacts_dir / "test.png"
        test_image.write_text("fake image")
        
        tool_bindings = ToolBindings()
        
        tool_call = ToolCall(
            id="call_4",
            name="upscale_image",
            arguments={
                "image_path": str(test_image),
                "scale": 2
            }
        )
        
        result = await tool_bindings.execute_tool(tool_call)
        
        assert isinstance(result, ArtifactResult)
        assert result.success == True
        assert "upscaled" in result.artifact_path
        assert result.data["scale"] == 2
        
        # Check file was created
        output_path = Path(result.artifact_path)
        assert output_path.exists()


# Test upload integration
class TestUploadIntegration:
    """Test upload tool integration."""
    
    @pytest.mark.asyncio
    async def test_upload_local(self, temp_artifacts_dir):
        """Test local file upload."""
        # Create test file
        test_file = temp_artifacts_dir / "test.txt"
        test_file.write_text("test content")
        
        tool_bindings = ToolBindings()
        
        tool_call = ToolCall(
            id="call_5",
            name="upload_file",
            arguments={
                "file_path": str(test_file),
                "destination": "local"
            }
        )
        
        with patch("ai.tools.bindings.Path.mkdir"):
            with patch("ai.tools.bindings.shutil.copy2") as mock_copy:
                result = await tool_bindings.execute_tool(tool_call)
                
                assert result.success == True
                assert result.data["source"] == str(test_file)
                assert "uploads" in result.data["destination"]
                mock_copy.assert_called_once()
                
    @pytest.mark.asyncio
    async def test_upload_telegram_not_implemented(self, tool_bindings):
        """Test telegram upload (not implemented)."""
        tool_call = ToolCall(
            id="call_6",
            name="upload_file",
            arguments={
                "file_path": "/test.txt",
                "destination": "telegram",
                "chat_id": "123456"
            }
        )
        
        result = await tool_bindings.execute_tool(tool_call)
        
        assert result.success == False
        assert "not yet implemented" in result.error
        
    @pytest.mark.asyncio
    async def test_upload_missing_file(self, tool_bindings):
        """Test upload with missing file."""
        tool_call = ToolCall(
            id="call_7",
            name="upload_file",
            arguments={
                "file_path": "/nonexistent/file.txt",
                "destination": "local"
            }
        )
        
        result = await tool_bindings.execute_tool(tool_call)
        
        assert result.success == False
        assert "not found" in result.error


# Test ASR integration
class TestASRIntegration:
    """Test ASR tool integration."""
    
    @pytest.mark.asyncio
    async def test_asr_transcribe_text(self, mock_asr_service, tool_bindings):
        """Test ASR transcription to text."""
        tool_call = ToolCall(
            id="call_8",
            name="transcribe_audio",
            arguments={
                "audio_path": "/path/to/audio.wav",
                "language": "en",
                "format": "text"
            }
        )
        
        result = await tool_bindings.execute_tool(tool_call)
        
        assert result.success == True
        assert result.data["text"] == "Hello world"
        assert result.data["language"] == "en"
        assert result.data["num_segments"] == 2
        
        mock_asr_service.transcribe_stream.assert_called_once_with(
            "/path/to/audio.wav",
            "en"
        )
        
    @pytest.mark.asyncio
    async def test_asr_transcribe_segments(self, mock_asr_service, tool_bindings):
        """Test ASR transcription with segments output."""
        tool_call = ToolCall(
            id="call_9",
            name="transcribe_audio",
            arguments={
                "audio_path": "/path/to/audio.wav",
                "language": "de",
                "format": "segments"
            }
        )
        
        result = await tool_bindings.execute_tool(tool_call)
        
        assert result.success == True
        assert len(result.data["segments"]) == 2
        assert result.data["segments"][0]["text"] == "Hello"
        assert result.metadata["format"] == "segments"


# Test TTS integration
class TestTTSIntegration:
    """Test TTS tool integration."""
    
    @pytest.mark.asyncio
    async def test_tts_synthesis(self, mock_voice_service, tool_bindings):
        """Test TTS synthesis."""
        tool_call = ToolCall(
            id="call_10",
            name="synthesize_speech",
            arguments={
                "text": "Hello world",
                "voice_profile": "emma",
                "language": "en",
                "backend": "openvoice"
            }
        )
        
        result = await tool_bindings.execute_tool(tool_call)
        
        assert isinstance(result, ArtifactResult)
        assert result.success == True
        assert result.artifact_path == "/artifacts/audio/synthesized.wav"
        assert result.artifact_type == "audio/wav"
        assert result.data["text"] == "Hello world"
        assert result.data["voice"] == "emma"
        
        mock_voice_service.synthesize.assert_called_once_with(
            "Hello world",
            "emma",
            "openvoice",
            "en"
        )
        
    @pytest.mark.asyncio
    async def test_tts_no_audio_returned(self, tool_bindings):
        """Test TTS when no audio is returned."""
        with patch("services.voice_service.VoiceService") as MockVoice:
            MockVoice.return_value.synthesize.return_value = None
            
            tool_call = ToolCall(
                id="call_11",
                name="synthesize_speech",
                arguments={
                    "text": "Test",
                    "voice_profile": "default"
                }
            )
            
            result = await tool_bindings.execute_tool(tool_call)
            
            assert result.success == False
            assert "no audio file" in result.error


# Test animation integration
class TestAnimationIntegration:
    """Test animation tool integration."""
    
    @pytest.mark.asyncio
    async def test_animation_generation(self, mock_anim_service, tool_bindings):
        """Test animation generation."""
        tool_call = ToolCall(
            id="call_12",
            name="generate_animation",
            arguments={
                "prompt": "A dancing robot",
                "duration": 5.0,
                "style": "cartoon"
            }
        )
        
        result = await tool_bindings.execute_tool(tool_call)
        
        assert isinstance(result, ArtifactResult)
        assert result.success == True
        assert result.artifact_path == "/artifacts/animations/animation.mp4"
        assert result.artifact_type == "video/mp4"
        assert result.data["prompt"] == "A dancing robot"
        assert result.data["duration"] == 5.0
        
        mock_anim_service.generate_animation.assert_called_once_with(
            "A dancing robot",
            5.0,
            "cartoon"
        )


# Test error handling
class TestErrorHandling:
    """Test error handling in tool execution."""
    
    @pytest.mark.asyncio
    async def test_unknown_tool(self, tool_bindings):
        """Test handling of unknown tool."""
        tool_call = ToolCall(
            id="call_13",
            name="unknown_tool",
            arguments={}
        )
        
        result = await tool_bindings.execute_tool(tool_call)
        
        assert result.success == False
        assert "Unknown tool" in result.error
        
    @pytest.mark.asyncio
    async def test_invalid_arguments(self, tool_bindings):
        """Test handling of invalid arguments."""
        tool_call = ToolCall(
            id="call_14",
            name="sd_generate",
            arguments={
                "width": "not_a_number"  # Invalid type
            }
        )
        
        result = await tool_bindings.execute_tool(tool_call)
        
        assert result.success == False
        assert result.error is not None
        
    @pytest.mark.asyncio
    async def test_service_initialization_error(self, tool_bindings):
        """Test service initialization error."""
        with patch("services.sd_service.SDService") as MockSD:
            MockSD.side_effect = Exception("Service init failed")
            
            tool_call = ToolCall(
                id="call_15",
                name="sd_generate",
                arguments={"prompt": "test"}
            )
            
            result = await tool_bindings.execute_tool(tool_call)
            
            assert result.success == False
            assert "Service init failed" in result.error


# Test end-to-end flow
class TestEndToEnd:
    """Test end-to-end tool execution flow."""
    
    @pytest.mark.asyncio
    async def test_tool_call_to_result(self, mock_sd_service):
        """Test complete flow from tool call to result."""
        # Create tool call
        tool_call = ToolCall(
            id="e2e_test",
            name="sd_generate",
            arguments={
                "prompt": "End-to-end test image",
                "width": 512,
                "height": 512
            }
        )
        
        # Execute using global function
        result = await execute_tool_call(tool_call)
        
        # Verify result
        assert isinstance(result, ArtifactResult)
        assert result.success == True
        assert result.artifact_path is not None
        assert result.metadata["service"] == "sd_service"
        assert result.metadata["method"] == "txt2img"
        
    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self, mock_sd_service, mock_voice_service):
        """Test executing multiple tool calls."""
        tool_calls = [
            ToolCall(
                id="multi_1",
                name="sd_generate",
                arguments={"prompt": "Image 1"}
            ),
            ToolCall(
                id="multi_2",
                name="synthesize_speech",
                arguments={"text": "Speech 1", "voice_profile": "default"}
            )
        ]
        
        results = []
        for tool_call in tool_calls:
            result = await execute_tool_call(tool_call)
            results.append(result)
            
        assert len(results) == 2
        assert all(r.success for r in results)
        assert isinstance(results[0], ArtifactResult)
        assert isinstance(results[1], ArtifactResult)
        assert results[0].artifact_type == "image/png"
        assert results[1].artifact_type == "audio/wav"


# Test global functions
class TestGlobalFunctions:
    """Test global convenience functions."""
    
    def test_get_available_tools(self):
        """Test getting available tools."""
        tools = get_available_tools()
        
        assert len(tools) >= 6  # At least 6 tools registered
        tool_names = [t for t in tools]
        assert "sd_generate" in tool_names
        assert "upscale_image" in tool_names
        assert "transcribe_audio" in tool_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])