# -*- coding: utf-8 -*-
"""
Unified Environment Variable Loader.

This module loads environment variables from a .env file and provides them as
Python constants. It includes a fallback mechanism for aliased variables.

Simply import this module at the beginning of an entry point to load and
access environment variables.

Example:
    import core.env
    print(core.env.OLLAMA_HOST)
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file located in the project root
# The search path starts from the current working directory and goes up.
load_dotenv()

def _first(*keys: str, default: str | None = None) -> str | None:
    """
    Return the value of the first environment variable that is set and not empty.

    Args:
        *keys: A sequence of environment variable names to check.
        default: The default value to return if no variable is found.

    Returns:
        The value of the first found environment variable, or the default value.
    """
    for key in keys:
        val = os.getenv(key)
        if val:
            return val
    return default

# --- General & Core ---
LOG_LEVEL: str = _first('LOG_LEVEL', default='INFO')
GCZ_CONFIG_PATH: str | None = _first('GCZ_CONFIG_PATH')
DEFAULT_MODEL: str = _first('DEFAULT_MODEL', default='llama3:latest')

# --- Ollama / Local LLMs ---
OLLAMA_HOST: str = _first('OLLAMA_HOST', 'OLLAMA_API_URL', default='http://localhost:11434')

# --- ComfyUI / Stable Diffusion Service ---
COMFYUI_URL: str = _first('COMFYUI_API_URL', 'COMFYUI_URL', default='127.0.0.1:8188')
COMFYUI_PATH: str | None = _first('COMFYUI_PATH')
DISABLE_COMFYUI_MANAGER_FRONT: bool = _first('DISABLE_COMFYUI_MANAGER_FRONT', default='0') == '1'

# --- Email Service ---
# Fallback logic for various email providers
EMAIL_USER: str | None = _first('GMAIL_USER', 'IMAP_USER', 'EMAIL_USER', 'SMTP_USER')
EMAIL_PASS: str | None = _first('GMAIL_PASS', 'IMAP_PASS', 'EMAIL_PASS', 'SMTP_PASS')
IMAP_HOST: str | None = _first('IMAP_HOST', 'GMAIL_IMAP_HOST')
SMTP_HOST: str | None = _first('SMTP_HOST', 'GMAIL_SMTP_HOST')
SMTP_PORT: int = int(_first('SMTP_PORT', default='587'))

# --- Telegram Bot ---
TELEGRAM_BOT_TOKEN: str | None = _first('TELEGRAM_BOT_TOKEN')

# --- External APIs & Services ---
OPENAI_API_KEY: str | None = _first('OPENAI_API_KEY')
GITHUB_TOKEN: str | None = _first('GITHUB_TOKEN')
IG_USERNAME: str | None = _first('IG_USERNAME')
IG_PASSWORD: str | None = _first('IG_PASSWORD')
YOUTUBE_CLIENT_SECRETS_FILE: str = _first('YOUTUBE_CLIENT_SECRETS_FILE', default='client_secret.json')

# --- Hardware & Performance ---
CUDA_VISIBLE_DEVICES: str | None = _first('CUDA_VISIBLE_DEVICES')
PATH_FFMPEG: str = _first('PATH_FFMPEG', default='ffmpeg')

# --- AI Model Paths & Configs ---
COQUI_TOS_AGREED: bool = _first('COQUI_TOS_AGREED', default='0') == '1'
TTS_HOME: str | None = _first('TTS_HOME')
TORTOISE_MODELS_DIR: str | None = _first('TORTOISE_MODELS_DIR')
HF_ENDPOINT: str = _first('HF_ENDPOINT', default='https://huggingface.co')
