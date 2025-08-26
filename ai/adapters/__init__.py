"""Adapters layer providing caching, provider abstraction and routing.

The sub-modules are designed to be **plug-compatible** with existing call
sites – the public API is **stable** and intentionally minimal.
"""

from __future__ import annotations

from .cache import PromptCache, EmbeddingCache
from .providers import Provider, StreamingResponse
from .router import get_provider_for_request

__all__ = [
    "PromptCache",
    "EmbeddingCache",
    "Provider",
    "StreamingResponse",
    "get_provider_for_request",
]