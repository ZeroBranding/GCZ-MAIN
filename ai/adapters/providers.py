from __future__ import annotations
"""Provider abstraction with streaming decode and resilient retries."""

import asyncio
import json
import os
import random
import time
from dataclasses import dataclass
from typing import AsyncIterator, Dict, Any, Optional, Callable

import aiohttp

from core.logging import logger

__all__ = [
    "Provider",
    "StreamingResponse",
]

_MAX_RETRIES = 3
_BASE_BACKOFF = 0.5  # seconds

# Fast JSON loader/dumper shortcuts -------------------------------------------
_dumps = lambda obj: json.dumps(obj, separators=(",", ":"))  # noqa: E731
_loads = json.loads


@dataclass
class StreamingResponse:
    """Wrapper around streaming token responses."""

    tokens: AsyncIterator[str]

    async def text(self) -> str:
        return "".join([token async for token in self.tokens])


class Provider:
    """Thin REST provider with streaming and retry support."""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or os.environ.get("PROVIDER_API_KEY")

    # ------------------------------------------------------------------
    async def _retry_call(self, func: Callable[[], Any]) -> Any:
        for attempt in range(_MAX_RETRIES):
            try:
                return await func()
            except Exception as exc:
                if attempt >= _MAX_RETRIES - 1:
                    raise
                backoff = _BASE_BACKOFF * (2 ** attempt) * random.uniform(0.8, 1.2)
                logger.warning(f"Call failed: {exc}; retrying in {backoff:.2f}s")
                await asyncio.sleep(backoff)

    # ------------------------------------------------------------------
    async def completion(self, prompt: str, stream: bool = False, **params: Any) -> Any:
        url = f"{self._base_url}/v1/completions"
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = {"prompt": prompt, **params, "stream": stream}

        async def _call():
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as sess:
                async with sess.post(url, headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    if stream:
                        return StreamingResponse(self._stream_tokens(resp))
                    return _loads(await resp.text())

        return await self._retry_call(_call)

    # ------------------------------------------------------------------
    async def _stream_tokens(self, resp: aiohttp.ClientResponse) -> AsyncIterator[str]:
        async for line_bytes in resp.content:
            line = line_bytes.decode()
            if not line.strip():
                continue
            # assume format: "data: {\"token\": \"...\"}"
            if line.startswith("data: "):
                try:
                    data = _loads(line[6:])
                    yield data.get("token", "")
                except json.JSONDecodeError:
                    continue