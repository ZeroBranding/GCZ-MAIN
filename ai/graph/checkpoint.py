from __future__ import annotations
"""Delta checkpointing utilities for LangGraph runtime.

The implementation focuses on **crash-safety**, **idempotency** and **minimal
write-amplification** by persisting only the *delta* between the previous state
and the new one.

The physical layout is a directory tree under the workspace:

    $WORKSPACE/data/graph/checkpoints/{session_id}.jsonl

Each line in the *JSON Lines* file represents a patch object of the following
shape::

    {
        "id": "<session_id>:<step_index>",
        "ts": "2024-06-23T12:34:56.789Z",
        "delta": { ... }  # json diff to apply in order
    }

A temp file is written first and then atomically renamed to guarantee that
crashes never leave a partially written checkpoint.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from core.logging import logger

__all__ = [
    "DeltaCheckpointer",
]

_WORKSPACE = Path(os.environ.get("WORKSPACE_PATH", "/workspace"))
_CHECKPOINT_DIR = _WORKSPACE / "data" / "graph" / "checkpoints"
_CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)


class DeltaCheckpointer:
    """Async-friendly checkpoint helper writing deltas as JSON-Lines."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._file_path = _CHECKPOINT_DIR / f"{session_id}.jsonl"
        # We lazily cache last full state after the first load.
        self._cached_state: Optional[Dict[str, Any]] = None
        self._lock = asyncio.Lock()

    # ---------------------------------------------------------------------
    # File helpers
    # ---------------------------------------------------------------------
    async def _read_lines(self) -> List[str]:
        if not self._file_path.exists():
            return []
        # Reading small text file is fast; do not hold lock.
        return self._file_path.read_text().splitlines()

    async def _write_lines(self, lines: List[str]) -> None:
        tmp_path = self._file_path.with_suffix(".tmp")
        tmp_path.write_text("\n".join(lines) + "\n")
        # Atomic replace on same FS.
        tmp_path.replace(self._file_path)

    # ------------------------------------------------------------------
    # Public API expected by core_graph (minimal subset)
    # ------------------------------------------------------------------
    async def aget(self) -> Optional[Dict[str, Any]]:  # noqa: D401 – simple name
        """Return last reconstructed state or None if no checkpoint."""
        async with self._lock:
            if self._cached_state is not None:
                return self._cached_state
            lines = await self._read_lines()
            if not lines:
                return None
            state: Dict[str, Any] = {}
            for line in lines:
                try:
                    patch = json.loads(line)
                    state.update(patch.get("delta", {}))
                except json.JSONDecodeError as exc:
                    logger.warning(f"Skipping corrupt checkpoint line: {exc}")
                    continue
            self._cached_state = state
            return state

    async def aput(self, new_state: Dict[str, Any]) -> None:
        """Write *delta* against last persisted state to disk."""
        async with self._lock:
            base_state = await self.aget() or {}
            delta = _dict_diff(base_state, new_state)
            if not delta:
                # No change → nothing to write.
                return
            record = {
                "id": new_state.get("session_id", "unknown") + f":{new_state.get('current_step', 0)}",
                "ts": datetime.utcnow().isoformat() + "Z",
                "delta": delta,
            }
            serialized = json.dumps(record, separators=(",", ":"))
            lines = await self._read_lines()
            lines.append(serialized)
            await self._write_lines(lines)
            self._cached_state = new_state.copy()

    # Convenience sync wrappers -------------------------------------------------
    def get(self) -> Optional[Dict[str, Any]]:
        return asyncio.run(self.aget())

    def put(self, state: Dict[str, Any]) -> None:
        asyncio.run(self.aput(state))


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _dict_diff(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Return *shallow* difference of dictionaries suitable for JSON patching."""
    diff: Dict[str, Any] = {}
    for k, v in new.items():
        if k not in old or old[k] != v:
            diff[k] = v
    # We purposely do not handle deletions – not required for current state model.
    return diff