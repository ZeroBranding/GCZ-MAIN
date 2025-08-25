from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, FilePath

# --- Base Path ---
BASE_DIR = Path(__file__).resolve().parent.parent

# --- Environment Loading ---
def load_env():
    """Loads environment variables from the .env file."""
    from dotenv import load_dotenv
    env_path = BASE_DIR / '.env'
    if not env_path.exists():
        raise FileNotFoundError(f".env file not found at {env_path}. Please copy .env.template and fill it out.")
    load_dotenv(dotenv_path=env_path)

load_env()

# --- Configuration Models ---

class PhoneConfig(BaseModel):
    sip_server: str
    sip_user: str
    audio_input_device: Optional[str] = None
    audio_output_device: Optional[str] = None
    vad_threshold: float = Field(0.5, ge=0, le=1)

class EmailConfig(BaseModel):
    confirm_before_send: bool = True
    gmail: dict
    icloud: dict

class AvatarConfig(BaseModel):
    sadtalker_checkpoints: FilePath
    esrgan_model_path: FilePath
    fps: int = Field(25, gt=0)
    bitrate: str = "5000k"

class SDConfig(BaseModel):
    use_directml: bool = True
    base_models_path: Path
    workflows_path: Path

class RoutingConfig(BaseModel):
    llm_planner: str
    llm_reviewer: str
    llm_docs: str
    llm_coder: str
    tts_backend: str
    asr_model: str
    sd_host: str
    sd_port: int

class TelegramConfig(BaseModel):
    bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    admin_ids: List[int]

class SocialConfig(BaseModel):
    instagram_username: str = Field(..., env="IG_USERNAME")
    instagram_password: str = Field(..., env="IG_PASSWORD")
    youtube_client_secrets_file: FilePath = Field(..., env="YOUTUBE_CLIENT_SECRETS_FILE")

class ToolEndpointConfig(BaseModel):
    name: str
    method: str
    base_url: Optional[str] = None
    path: Optional[str] = None
    timeout_s: int = 60
    module: Optional[str] = None
    function: Optional[str] = None

class ToolsConfig(BaseModel):
    tool_endpoints: List[ToolEndpointConfig]


# --- Loading Logic ---

def load_yaml(name: str) -> dict:
    """Loads a YAML configuration file from the configs directory."""
    config_path = BASE_DIR / 'configs' / f'{name}.yml'
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file '{name}.yml' not found in {config_path.parent}")
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def load_config(name: str, model: BaseModel) -> BaseModel:
    """Loads a YAML file and validates it with the given Pydantic model."""
    data = load_yaml(name)
    return model.model_validate(data)

# --- Example Usage (can be removed) ---
if __name__ == "__main__":
    try:
        telegram_conf = TelegramConfig.model_validate(load_yaml('telegram'))
        print("Telegram Config Loaded:")
        print(telegram_conf)

        routing_conf = load_config('routing', RoutingConfig)
        print("\nRouting Config Loaded:")
        print(routing_conf)

    except Exception as e:
        print(f"An error occurred: {e}")
