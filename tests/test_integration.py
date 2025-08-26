import pytest
import asyncio
from unittest.mock import AsyncMock, patch

import os
import sys

# We need to modify the path to import from the app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set a dummy token for initialization
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:ABC-DEF1234567890"

import telegram
from telegram import Update
from telegram.ext import ContextTypes

# Import the bot handlers
from telegram_bot import generate_image

@pytest.mark.asyncio
@patch('telegram_bot.start_graph', new_callable=AsyncMock)
async def test_img_command_integration(mock_start_graph):
    """
    Tests that the /img command correctly parses the prompt and calls the
    graph entry point with the right parameters.
    """
    # --- Arrange ---
    # Mock the Telegram Update object
    update = MagicMock()
    update.effective_user.id = 12345
    update.effective_chat.id = 67890

    # Mock the context object with arguments
    context = MagicMock()
    context.args = ["a", "test", "prompt"]

    # --- Act ---
    await generate_image(update, context)

    # --- Assert ---
    # Verify that the initial "request received" message was sent
    update.message.reply_text.assert_called_once()
    assert "wird geplant" in update.message.reply_text.call_args[0][0]

    # Verify that start_graph was called
    mock_start_graph.assert_awaited_once()

    # Verify the arguments passed to start_graph
    call_args = mock_start_graph.call_args
    assert "session_id" in call_args.kwargs
    assert call_args.kwargs["goal"] == "Generate an image with the prompt: 'a test prompt'"

    user_ctx = call_args.kwargs["user_ctx"]
    assert user_ctx["user_id"] == "12345"
    assert user_ctx["chat_id"] == "67890"
