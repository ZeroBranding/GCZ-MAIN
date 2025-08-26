from __future__ import annotations
"""Lightweight no-op metrics hooks.

This module intentionally contains **no external dependencies** and exports
asynchronous functions that can be monkey-patched by a metrics backend at
runtime.  The default implementation is a best-effort no-op so that imports
are cheap and do not impact critical path execution.

Public API (stable):
    async graph_active(session_id: str, active: bool) -> None
    async node_latency(node: str, latency_ms: float) -> None
    async queue_depth(depth: int) -> None

These coroutines MUST NOT raise – any exception will be swallowed by callers.
"""

import asyncio
from typing import Any

__all__ = [
    "graph_active",
    "node_latency",
    "queue_depth",
]


async def _noop(*_args: Any, **_kwargs: Any) -> None:  # pragma: no cover
    """Default coroutine that does nothing."""
    # Yield to event-loop to keep behaviour asynchronous but cheap.
    await asyncio.sleep(0)


# Assign public symbols to noop implementations.  At runtime, an external
# component (e.g. Prometheus exporter) may monkey-patch these names with
# real implementations.

graph_active = _noop  # type: ignore
node_latency = _noop  # type: ignore
queue_depth = _noop  # type: ignore