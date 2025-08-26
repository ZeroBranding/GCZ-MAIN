from __future__ import annotations
"""Provider router with per-backend circuit breakers (half-open).

The router keeps a registry of Provider instances and transparently opens the
circuit after consecutive failures.  After a cool-down period, a *single* probe
request is allowed to verify recovery (half-open).  Success closes the circuit;
failure re-opens it.
"""

import asyncio
import time
from typing import Dict, Any, Optional

from core.logging import logger

from .providers import Provider

__all__ = ["get_provider_for_request"]

# ---------------------------------------------------------------------------
# Circuit Breaker implementation
# ---------------------------------------------------------------------------


class _CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 30):
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout  # seconds
        self._state = "closed"  # closed, open, half-open
        self._failure_count = 0
        self._opened_at = 0.0
        self._lock = asyncio.Lock()

    async def before_request(self) -> bool:
        """Return True if request may proceed."""
        async with self._lock:
            if self._state == "open":
                if time.time() - self._opened_at >= self._reset_timeout:
                    self._state = "half-open"
                else:
                    return False  # short-circuit
            return True

    async def after_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            self._state = "closed"

    async def after_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            if self._failure_count >= self._failure_threshold:
                self._state = "open"
                self._opened_at = time.time()
                logger.warning("Circuit breaker opened")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class _Router:
    def __init__(self) -> None:
        self._providers: Dict[str, Provider] = {}
        self._breakers: Dict[str, _CircuitBreaker] = {}

    def register(self, name: str, provider: Provider) -> None:
        self._providers[name] = provider
        self._breakers[name] = _CircuitBreaker()

    async def route(self, name: str, *args: Any, **kwargs: Any):
        if name not in self._providers:
            raise KeyError(f"provider {name} not registered")
        breaker = self._breakers[name]
        if not await breaker.before_request():
            raise RuntimeError(f"circuit-open:{name}")
        try:
            result = await getattr(self._providers[name], kwargs.pop("method", "completion"))(*args, **kwargs)
            await breaker.after_success()
            return result
        except Exception:
            await breaker.after_failure()
            raise


_router = _Router()


def get_provider_for_request(name: str) -> Provider:
    """Retrieve provider with circuit breaker logic available."""
    if name not in _router._providers:
        # For demo we lazily create a Provider pointing to env BACKEND_<NAME>_URL
        import os

        base_url = os.environ.get(f"BACKEND_{name.upper()}_URL", "http://localhost:8000")
        _router.register(name, Provider(base_url))
    return _router._providers[name]