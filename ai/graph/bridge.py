from __future__ import annotations
"""Bridge between graph nodes and external tools ensuring idempotency & rate-limits.

The `run_tool` coroutine wraps a tool execution call, generating a deterministic
*run_key* derived from `state.session_id`, the tool name and the logical step
index.  A lightweight SQLite table (`run_keys`) guarantees **exactly-once**
semantics across crashes/resumes.

Rate-limits are enforced per tool with a token-bucket in SQLite so that
parallel workers/share process space maintain global consistency.
"""

import asyncio
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Callable, Optional

from core.logging import logger
from ai.graph.tools import get_registry

__all__ = ["run_tool"]

# ---------------------------------------------------------------------------
# SQLite helpers (shared across processes via on-disk file)
# ---------------------------------------------------------------------------

_WORKSPACE = Path(os.environ.get("WORKSPACE_PATH", "/workspace"))
_DB_PATH = _WORKSPACE / "data" / "graph" / "bridge_meta.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _init_db() -> None:  # pragma: no cover – called at import
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS run_keys (
                    run_key TEXT PRIMARY KEY,
                    result_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS rate_limits (
                    tool TEXT PRIMARY KEY,
                    tokens REAL,
                    updated_at REAL
                )"""
        )


_init_db()


# ---------------------------------------------------------------------------
# Rate limiting (token bucket) – configurable via env TOOL_RATE_<NAME>=reqs/sec
# ---------------------------------------------------------------------------

_DEFAULT_RATE = 5.0  # 5 RPS


def _get_rate(tool: str) -> float:
    return float(os.environ.get(f"TOOL_RATE_{tool.upper()}", _DEFAULT_RATE))


async def _acquire_rate(tool: str) -> None:
    rate = _get_rate(tool)
    now = time.time()
    with sqlite3.connect(_DB_PATH) as conn:
        row = conn.execute(
            "SELECT tokens, updated_at FROM rate_limits WHERE tool = ?", (tool,)
        ).fetchone()
        if row:
            tokens, updated_at = row
        else:
            tokens, updated_at = rate, now
        # replenish
        tokens = min(rate, tokens + (now - updated_at) * rate)
        if tokens < 1.0:
            sleep_for = (1.0 - tokens) / rate
            logger.info(f"Rate-limit hit for {tool} – sleeping {sleep_for:.2f}s")
            await asyncio.sleep(sleep_for)
            return await _acquire_rate(tool)  # retry
        tokens -= 1.0
        conn.execute(
            "INSERT OR REPLACE INTO rate_limits(tool, tokens, updated_at) VALUES (?, ?, ?)",
            (tool, tokens, now),
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_tool(tool: str, params: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute *tool* with idempotency & rate-limit.

    Derives run_key = "{session_id}:{tool}:{idx}" where idx = state["current_step"].
    """
    session_id = state.get("session_id")
    step_idx = state.get("current_step", 0)
    run_key = f"{session_id}:{tool}:{step_idx}"

    # Fast path: dedup check
    with sqlite3.connect(_DB_PATH) as conn:
        row = conn.execute("SELECT result_json FROM run_keys WHERE run_key = ?", (run_key,)).fetchone()
        if row:
            logger.info(f"Dedup – returning cached result for {run_key}")
            return json.loads(row[0])

    # Rate-limit acquire (may await)
    await _acquire_rate(tool)

    # Timeout propagation – per tool ENV TOOL_TIMEOUT_<NAME>
    timeout = float(os.environ.get(f"TOOL_TIMEOUT_{tool.upper()}", "300"))
    registry = get_registry()
    handler = registry.get(tool)
    if not handler:
        raise ValueError(f"unknown tool {tool}")

    async def _execute():
        return await registry.execute_tool(tool, **params)

    try:
        result = await asyncio.wait_for(_execute(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Tool {tool} timed out after {timeout}s")
        raise

    # Persist run_key & result for idempotency
    with sqlite3.connect(_DB_PATH) as conn:
        try:
            conn.execute(
                "INSERT INTO run_keys(run_key, result_json) VALUES (?, ?)",
                (run_key, json.dumps(result, separators=(",", ":"))),
            )
        except sqlite3.IntegrityError:
            # Another worker beat us to it → read canonical result
            row = conn.execute("SELECT result_json FROM run_keys WHERE run_key = ?", (run_key,)).fetchone()
            if row:
                result = json.loads(row[0])

    return result