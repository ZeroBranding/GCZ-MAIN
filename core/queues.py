# -*- coding: utf-8 -*-
"""
Global, in-memory queues for inter-service communication.

This provides a simple, decoupled way for different parts of the application
to send messages to each other without direct dependencies.
"""

import asyncio

# Queue for messages that should be automatically sent by the Telegram bot
telegram_autosend_queue = asyncio.Queue()
