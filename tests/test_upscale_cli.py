"""Tests for Upscale CLI and Service."""
import pytest
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open
import urllib.error

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.upscale_service import (
    ComfyClient,
    UpscaleService,
    main
)
from core.errors import ExternalToolError


# Fixtures
@pytest.fixture
def mock_comfy_server():
    """Mock ComfyUI server responses."""
    with patch('urllib.request.urlopen') as mock_urlopen:
        # Create mock response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            'prompt_id': 'test_prompt_123'
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        
        mock_urlopen.return_value = mock_response
        yield mock_urlopen


@pytest.fixture
def temp_image():
    """Create a temporary test image."""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        # Write minimal PNG header
        f.write(b'\x89PNG\r\n\x1a\n')
        temp_path = f.name
        
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = {
        'presets': {
            'default_scale': 4,
            'unsharp': False
        },
        'models': {
            'RealESRGAN_x4': {
                'scale': 4,
                'file': 'RealESRGAN_x4.pth'
            }
        }
    }
    return config


# Test ComfyClient
class TestComfyClient:
    """Test ComfyUI client functionality."""
    
    def test_client_initialization(self):
        """Test client initialization."""
        client = ComfyClient()
        assert client.server_address == "127.0.0.1:8188"
        assert client.client_id is not None
        
    def test_client_with_custom_server(self):
        """Test client with custom server address."""
        client = ComfyClient("192.168.1.100:8188")
        assert client.server_address == "192.168.1.100:8188"
        
    def test_post_workflow(self, mock_comfy_server):
        """Test posting workflow to ComfyUI."""
        client = ComfyClient()
        workflow = {"1": {"class_type": "LoadImage"}}
        inputs = {}
        
        prompt_id = client._post(workflow, inputs)
        
        assert prompt_id == "test_prompt_123"
        mock_comfy_server.assert_called_once()
        
    def test_post_workflow_error(self):
        """Test error handling in workflow posting."""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
            
            client = ComfyClient()
            workflow = {"1": {"class_type": "LoadImage"}}
            
            with pytest.raises(ExternalToolError) as exc_info:
                client._post(workflow, {})
                
            assert "Failed to queue prompt" in str(exc_info.value)
            
    def test_poll_success(self, mock_comfy_server):
        """Test successful polling for job completion."""
        # Setup mock to return history with outputs
        mock_comfy_server.return_value.read.return_value = json.dumps({
            "test_job_123": {
                "outputs": {
                    "3": {
                        "images": [{
                            "filename": "output.png",
                            "subfolder": "",
                            "type": "output"
                        }]
                    }
                }
            }
        }).encode('utf-8')
        
        client = ComfyClient()
        outputs = client._poll("test_job_123", timeout=1)
        
        assert "3" in outputs
        assert "images" in outputs["3"]
        
    def test_poll_timeout(self, mock_comfy_server):
        """Test polling timeout."""
        # Setup mock to return empty history
        mock_comfy_server.return_value.read.return_value = json.dumps({}).encode('utf-8')
        
        client = ComfyClient()
        
        with pytest.raises(ExternalToolError) as exc_info:
            client._poll("test_job_123", timeout=0.1)
            
        assert "timed out" in str(exc_info.value)
        
    def test_get_image(self, mock_comfy_server):
        """Test image download from ComfyUI."""
        # Setup mock to return image data
        mock_comfy_server.return_value.read.return_value = b"fake_image_data"
        
        client = ComfyClient()
        image_data = client.get_image("test.png", "", "output")
        
        assert image_data == b"fake_image_data"
        mock_comfy_server.assert_called_once()


# Test UpscaleService
class TestUpscaleService:
    """Test upscale service functionality."""
    
    def test_service_initialization(self, mock_config):
        """Test service initialization."""
        with patch.object(UpscaleService, '_load_config', return_value=mock_config):
            service = UpscaleService()
            
            assert service.default_scale == 4
            assert service.unsharp == False
            assert service.artifacts_dir.name == "upscaled"
            
    def test_load_config_file(self, temp_output_dir, mock_config):
        """Test loading configuration from file."""
        config_path = Path(temp_output_dir) / "upscale.yml"
        
        import yaml
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
            
        service = UpscaleService(config_path=str(config_path))
        assert service.default_scale == 4
        
    def test_create_upscale_workflow(self):
        """Test workflow creation."""
        service = UpscaleService()
        workflow = service._create_upscale_workflow(scale=4)
        
        assert "1" in workflow  # LoadImage
        assert "2" in workflow  # ImageUpscaleWithModel
        assert "3" in workflow  # SaveImage
        assert workflow["2"]["inputs"]["upscale_model"] == "RealESRGAN_x4.pth"
        
    def test_upscale_success(self, temp_image, temp_output_dir, mock_comfy_server):
        """Test successful image upscaling."""
        # Setup mocks
        with patch.object(ComfyClient, 'upload_image', return_value=("test.png", "")):
            with patch.object(ComfyClient, '_post', return_value="job_123"):
                with patch.object(ComfyClient, '_poll') as mock_poll:
                    mock_poll.return_value = {
                        "3": {
                            "images": [{
                                "filename": "upscaled.png",
                                "subfolder": "",
                                "type": "output"
                            }]
                        }
                    }
                    
                    with patch.object(ComfyClient, 'get_image', return_value=b"upscaled_data"):
                        service = UpscaleService()
                        service.artifacts_dir = Path(temp_output_dir)
                        
                        result = service.upscale(
                            image_path=temp_image,
                            scale=4
                        )
                        
                        assert result["scale"] == 4
                        assert "output_path" in result
                        assert result["input_path"] == str(Path(temp_image).resolve())
                        assert result["duration"] > 0
                        
                        # Check file was saved
                        output_path = Path(result["output_path"])
                        assert output_path.exists()
                        
    def test_upscale_invalid_scale(self, temp_image):
        """Test upscaling with invalid scale."""
        service = UpscaleService()
        
        with pytest.raises(ValueError) as exc_info:
            service.upscale(temp_image, scale=3)
            
        assert "Invalid scale" in str(exc_info.value)
        
    def test_upscale_missing_file(self):
        """Test upscaling with missing input file."""
        service = UpscaleService()
        
        with pytest.raises(FileNotFoundError) as exc_info:
            service.upscale("/nonexistent/image.png")
            
        assert "Input image not found" in str(exc_info.value)
        
    def test_upscale_with_custom_output(self, temp_image, temp_output_dir, mock_comfy_server):
        """Test upscaling with custom output path."""
        output_path = Path(temp_output_dir) / "custom_output.png"
        
        with patch.object(ComfyClient, 'upload_image', return_value=("test.png", "")):
            with patch.object(ComfyClient, '_post', return_value="job_123"):
                with patch.object(ComfyClient, '_poll') as mock_poll:
                    mock_poll.return_value = {
                        "3": {
                            "images": [{
                                "filename": "upscaled.png",
                                "subfolder": "",
                                "type": "output"
                            }]
                        }
                    }
                    
                    with patch.object(ComfyClient, 'get_image', return_value=b"upscaled_data"):
                        service = UpscaleService()
                        
                        result = service.upscale(
                            image_path=temp_image,
                            scale=2,
                            output_path=str(output_path)
                        )
                        
                        assert result["output_path"] == str(output_path)
                        assert output_path.exists()


# Test CLI
class TestCLI:
    """Test CLI functionality."""
    
    def test_cli_help(self):
        """Test CLI help output."""
        with patch('sys.argv', ['upscale_service.py', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            
    def test_cli_missing_input(self):
        """Test CLI with missing input argument."""
        with patch('sys.argv', ['upscale_service.py']):
            with pytest.raises(SystemExit):
                main()
                
    def test_cli_success(self, temp_image, temp_output_dir, mock_comfy_server):
        """Test successful CLI execution."""
        output_path = Path(temp_output_dir) / "output.png"
        
        with patch('sys.argv', [
            'upscale_service.py',
            '--in', temp_image,
            '--scale', '2',
            '--out', str(output_path)
        ]):
            with patch.object(UpscaleService, 'upscale') as mock_upscale:
                mock_upscale.return_value = {
                    'output_path': str(output_path),
                    'scale': 2,
                    'duration': 1.5,
                    'model': 'RealESRGAN_x2'
                }
                
                exit_code = main()
                
                assert exit_code == 0
                mock_upscale.assert_called_once_with(
                    image_path=temp_image,
                    scale=2,
                    output_path=str(output_path),
                    model=None
                )
                
    def test_cli_file_not_found(self):
        """Test CLI with nonexistent input file."""
        with patch('sys.argv', [
            'upscale_service.py',
            '--in', '/nonexistent/image.png'
        ]):
            with patch.object(UpscaleService, 'upscale') as mock_upscale:
                mock_upscale.side_effect = FileNotFoundError("File not found")
                
                exit_code = main()
                assert exit_code == 1
                
    def test_cli_invalid_scale(self, temp_image):
        """Test CLI with invalid scale value."""
        with patch('sys.argv', [
            'upscale_service.py',
            '--in', temp_image,
            '--scale', '3'
        ]):
            with pytest.raises(SystemExit):
                main()
                
    def test_cli_comfy_error(self, temp_image):
        """Test CLI with ComfyUI error."""
        with patch('sys.argv', [
            'upscale_service.py',
            '--in', temp_image
        ]):
            with patch.object(UpscaleService, 'upscale') as mock_upscale:
                mock_upscale.side_effect = ExternalToolError("ComfyUI connection failed")
                
                exit_code = main()
                assert exit_code == 2
                
    def test_cli_verbose_mode(self, temp_image):
        """Test CLI with verbose mode."""
        with patch('sys.argv', [
            'upscale_service.py',
            '--in', temp_image,
            '--verbose'
        ]):
            with patch.object(UpscaleService, 'upscale') as mock_upscale:
                mock_upscale.return_value = {
                    'output_path': '/tmp/output.png',
                    'scale': 4,
                    'duration': 2.0,
                    'model': 'RealESRGAN_x4'
                }
                
                with patch('logging.basicConfig') as mock_logging:
                    exit_code = main()
                    
                    assert exit_code == 0
                    mock_logging.assert_called_once()
                    
    def test_cli_with_server_override(self, temp_image):
        """Test CLI with server address override."""
        with patch('sys.argv', [
            'upscale_service.py',
            '--in', temp_image,
            '--server', '192.168.1.100:8188'
        ]):
            with patch.object(UpscaleService, 'upscale') as mock_upscale:
                mock_upscale.return_value = {
                    'output_path': '/tmp/output.png',
                    'scale': 4,
                    'duration': 1.0,
                    'model': 'RealESRGAN_x4'
                }
                
                exit_code = main()
                
                assert exit_code == 0
                assert os.environ.get('COMFYUI_URL') == '192.168.1.100:8188'


# Test Integration
class TestIntegration:
    """Integration tests."""
    
    def test_end_to_end_upscale(self, temp_image, temp_output_dir):
        """Test end-to-end upscaling workflow."""
        with patch.object(ComfyClient, 'upload_image', return_value=("test.png", "")):
            with patch.object(ComfyClient, '_post', return_value="job_123"):
                with patch.object(ComfyClient, '_poll') as mock_poll:
                    mock_poll.return_value = {
                        "3": {
                            "images": [{
                                "filename": "result.png",
                                "subfolder": "",
                                "type": "output"
                            }]
                        }
                    }
                    
                    with patch.object(ComfyClient, 'get_image', return_value=b"result_data"):
                        # Initialize service
                        service = UpscaleService()
                        service.artifacts_dir = Path(temp_output_dir)
                        
                        # Perform upscale
                        result = service.upscale(temp_image, scale=4)
                        
                        # Verify result
                        assert result["scale"] == 4
                        assert Path(result["output_path"]).exists()
                        
                        # Verify logged metadata
                        assert result["model"] == "RealESRGAN_x4"
                        assert result["duration"] > 0
                        
    def test_sd_service_integration(self):
        """Test integration with SD service."""
        from services.sd_service import SDService
        
        with patch.object(ComfyClient, 'upload_image', return_value=("test.png", "")):
            with patch.object(ComfyClient, '_post', return_value="job_123"):
                with patch.object(ComfyClient, '_poll') as mock_poll:
                    mock_poll.return_value = {
                        "3": {
                            "images": [{
                                "filename": "result.png",
                                "subfolder": "",
                                "type": "output"
                            }]
                        }
                    }
                    
                    with patch.object(ComfyClient, 'get_image', return_value=b"result_data"):
                        sd_service = SDService()
                        
                        # Test that upscale method works
                        with tempfile.NamedTemporaryFile(suffix='.png') as f:
                            result = sd_service.upscale(f.name, scale=2)
                            
                            assert "path" in result
                            assert result["meta"]["scale"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])