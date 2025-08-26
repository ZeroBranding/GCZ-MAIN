import logging
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Base Path ---
BASE_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)

# --- Environment-based Settings ---

class AppSettings(BaseSettings):
    """
    Main application settings loaded from environment variables.
    The .env file is loaded automatically by pydantic-settings.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # --- Core Required Settings ---
    TELEGRAM_BOT_TOKEN: str = Field(..., description="Your Telegram Bot API Token from @BotFather.")

    # --- General & Core ---
    LOG_LEVEL: str = Field("INFO", description="Log level for the application (e.g., DEBUG, INFO, WARNING, ERROR)")
    GCZ_CONFIG_PATH: Optional[str] = Field(None, description="Optional: Path to a specific YAML configuration file.")
    DEFAULT_MODEL: str = Field("llama3:latest", description="The default model to be used by agents.")

    # --- Ollama / Local LLMs ---
    OLLAMA_HOST: str = Field("http://localhost:11434", description="The full URL of your Ollama server.")

    # --- ComfyUI / Stable Diffusion Service ---
    COMFYUI_URL: str = Field("127.0.0.1:8188", description="The address and port of the ComfyUI API.")
    COMFYUI_PATH: Optional[str] = Field(None, description="Optional: Absolute path to your ComfyUI installation.")
    DISABLE_COMFYUI_MANAGER_FRONT: bool = Field(False, description="Optional: Set to true to disable the ComfyUI-Manager frontend.")

    # --- Email Service ---
    EMAIL_USER: Optional[str] = Field(None, alias="GMAIL_USER")
    EMAIL_PASS: Optional[str] = Field(None, alias="GMAIL_PASS")
    IMAP_HOST: Optional[str] = Field(None, alias="GMAIL_IMAP_HOST")
    SMTP_HOST: Optional[str] = Field(None, alias="GMAIL_SMTP_HOST")
    SMTP_PORT: int = Field(587)

    # --- External APIs & Services ---
    OPENAI_API_KEY: Optional[str] = Field(None)
    GITHUB_TOKEN: Optional[str] = Field(None)
    IG_USERNAME: Optional[str] = Field(None)
    IG_PASSWORD: Optional[str] = Field(None)
    YOUTUBE_CLIENT_SECRETS_FILE: Optional[str] = Field(None)

    # --- Hardware & Performance ---
    CUDA_VISIBLE_DEVICES: Optional[str] = Field(None)
    PATH_FFMPEG: str = Field("ffmpeg", description="Path to the ffmpeg executable.")

    # --- Media & Artifact Handling ---
    SAVE_MEDIA_LOCALLY: bool = Field(True)
    TELEGRAM_SEND_IMAGES: bool = Field(True)
    TELEGRAM_SEND_VIDEOS: bool = Field(True)

# --- YAML-based Configuration Models ---

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
    admin_ids: List[int]

# --- Main Config Object ---

class Config:
    """
    A unified configuration object.
    """
    def __init__(self):
        try:
            self.app = AppSettings()
        except ValidationError as e:
            missing_vars = [err['loc'][0] for err in e.errors() if 'value_error.missing' in str(err['msg'])]
            if missing_vars:
                logger.critical(
                    "FATAL: Missing required environment variables.\n"
                    "Please copy '.env.template' to '.env' and fill in the following values:\n"
                    f"{', '.join(v for v in missing_vars)}"
                )
                exit(1)
            else:
                logger.critical(f"FATAL: Configuration validation error: {e}")
                exit(1)

        self.routing: RoutingConfig = self._load_yaml('routing', RoutingConfig)
        self.telegram: TelegramConfig = self._load_yaml('telegram', TelegramConfig)

    def _load_yaml(self, name: str, model: BaseModel) -> BaseModel:
        """Loads a YAML file and validates it with the given Pydantic model."""
        config_path = BASE_DIR / 'configs' / f'{name}.yml'
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file '{name}.yml' not found in {config_path.parent}")
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        return model.model_validate(data)

# --- Global Config Instance ---
_settings_instance = None

def get_settings() -> Config:
    """
    Returns a singleton instance of the Config object.
    This function controls when the settings are loaded and validated,
    making the application more testable.
    """
    global _settings_instance
    if _settings_instance is None:
        try:
            _settings_instance = Config()
        except FileNotFoundError as e:
            logger.critical(f"FATAL: Could not load configuration. {e}")
            exit(1)
        except Exception as e:
            logger.critical(f"An unexpected error occurred during configuration loading: {e}")
            exit(1)
    return _settings_instance

# The settings object should be retrieved by calling get_settings() in the
# application modules. This prevents the settings from being loaded and
# validated when the module is imported by tests.
