import os
import shutil

import pytest

from services.voice_service import VoiceProfile, VoiceService

# --- Test Setup ---
TEST_PROFILE_DIR = "models/voice_test"
TEST_OUTPUT_DIR = "artifacts/tts_test"
PIPER_MODEL_DIR = "models/piper_test"
PIPER_MODEL_NAME = "de_DE-thorsten-medium"

@pytest.fixture(scope="module")
def voice_service():
    """Fixture to set up and tear down the VoiceService for testing."""
    # Override config for testing
    os.environ["GCZ_CONFIG_PATH"] = "configs/test_voice.yml"
    with open("configs/test_voice.yml", "w") as f:
        f.write(f"""
voice:
  profile_dir: {TEST_PROFILE_DIR}
  output_dir: {TEST_OUTPUT_DIR}
  piper_model_dir: {PIPER_MODEL_DIR}
""")

    # Create dummy directories
    os.makedirs(TEST_PROFILE_DIR, exist_ok=True)
    os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)
    os.makedirs(PIPER_MODEL_DIR, exist_ok=True)

    # Note: This test requires a real Piper model to be present.
    # We will check for it and skip if not found.
    piper_model_path = os.path.join(PIPER_MODEL_DIR, f"{PIPER_MODEL_NAME}.onnx")
    if not os.path.exists(piper_model_path):
        pytest.skip(f"Piper model not found at {piper_model_path}. Download it for this test.")

    service = VoiceService()
    yield service

    # Teardown
    shutil.rmtree(TEST_PROFILE_DIR)
    shutil.rmtree(TEST_OUTPUT_DIR)
    shutil.rmtree(PIPER_MODEL_DIR)
    os.remove("configs/test_voice.yml")
    del os.environ["GCZ_CONFIG_PATH"]

# --- Tests ---

def test_piper_synthesis_short(voice_service: VoiceService):
    """
    Tests a short synthesis using the Piper backend.
    This is a quick test to ensure the service and model loading works.
    """
    # Arrange
    profile_name = "test_piper_profile"
    text = "Hallo."

    # Create a dummy profile for the test
    profile = VoiceProfile(profile_name, TEST_PROFILE_DIR)
    profile.set("piper_model", PIPER_MODEL_NAME)

    # Act
    output_path = voice_service.synthesize(
        text=text,
        voice_profile_name=profile_name,
        backend='piper'
    )

    # Assert
    assert output_path is not None
    assert os.path.exists(output_path)
    assert os.path.getsize(output_path) > 1000  # Check that the file is not empty

    # Check if the file is a valid WAV file (simple check)
    with open(output_path, 'rb') as f:
        header = f.read(4)
        assert header == b'RIFF'

    print(f"Piper synthesis test successful. Output at: {output_path}")
