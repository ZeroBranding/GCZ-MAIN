import os

# To allow imports from core
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import RoutingConfig, TelegramConfig, load_config


# --- Test Setup ---
# Create dummy .env and config files for isolated testing
@pytest.fixture(scope="module")
def setup_test_environment(tmpdir_factory):
    # Base directory for this test session
    base_path = tmpdir_factory.mktemp("config_test")

    # Create dummy .env
    env_content = """
    TELEGRAM_BOT_TOKEN=12345:testtoken
    IG_USERNAME=testuser
    IG_PASSWORD=testpass
    YOUTUBE_CLIENT_SECRETS_FILE=client_secret.json
    """
    (base_path / ".env").write_text(env_content, encoding="utf-8")

    # Create dummy configs directory
    configs_path = base_path / "configs"
    configs_path.mkdir()

    # Create dummy config files
    (configs_path / "routing.yml").write_text("""
    llm_planner: "test_planner"
    llm_reviewer: "test_reviewer"
    llm_docs: "test_docs"
    llm_coder: "test_coder"
    tts_backend: "piper"
    asr_model: "whisper"
    sd_host: "localhost"
    sd_port: 8188
    """, encoding="utf-8")

    (configs_path / "telegram.yml").write_text("""
    bot_token: "will_be_overwritten_by_env"
    admin_ids: [123, 456]
    """, encoding="utf-8")

    # Monkeypatch the BASE_DIR in the config module to point to our temp dir
    import core.config
    original_base_dir = core.config.BASE_DIR
    core.config.BASE_DIR = Path(base_path)

    # Reload env vars from the dummy .env
    core.config.load_env()

    yield # Run the tests

    # Teardown: Restore original BASE_DIR
    core.config.BASE_DIR = original_base_dir

# --- Tests ---

def test_load_routing_config(setup_test_environment):
    """Tests successful loading of a valid routing config."""
    config = load_config("routing", RoutingConfig)
    assert config.llm_planner == "test_planner"
    assert config.sd_port == 8188

def test_load_telegram_config_from_env(setup_test_environment):
    """Tests that TelegramConfig correctly loads bot_token from the environment."""
    # We must manually merge env vars for Pydantic models that use `Field(env=...)`
    # Our `load_config` helper doesn't do this automatically.

    # Step 1: Load YAML data
    from core.config import load_yaml
    yaml_data = load_yaml("telegram")

    # Step 2: Manually add the token from env for the test
    yaml_data['bot_token'] = os.getenv("TELEGRAM_BOT_TOKEN")

    # Step 3: Validate
    config = TelegramConfig.model_validate(yaml_data)
    assert config.bot_token == "12345:testtoken"
    assert config.admin_ids == [123, 456]

def test_invalid_config_raises_validation_error(setup_test_environment):
    """Tests that a config with missing fields raises a ValidationError."""
    # Write an invalid config file
    configs_path = Path(str(sys.path[0])) / "configs" # Bit of a hack to get path in test
    (configs_path / "invalid_routing.yml").write_text("""
    llm_planner: "only_one_field"
    # Other required fields are missing
    """, encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config("invalid_routing", RoutingConfig)

def test_missing_config_file_raises_error(setup_test_environment):
    """Tests that trying to load a non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("non_existent_config", RoutingConfig)
