from __future__ import annotations
"""Caching utilities for adapter layer.

PromptCache – short-lived in-memory cache keyed by **prompt str**.
EmbeddingCache – persistent LFU cache stored in an on-disk SQLite DB.  Each
vector row is keyed by a SHA256 of the text to keep keys short.
"""

import asyncio
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Dict, Tuple, Any, Optional

from core.logging import logger

__all__ = [
    "PromptCache",
    "EmbeddingCache",
]


class PromptCache:
    """Simple asyncio-safe TTL cache for prompts → response."""

    def __init__(self, ttl_sec: int = 300, max_size: int = 2048) -> None:
        self._ttl = ttl_sec
        self._max_size = max_size
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            ts, val = entry
            if time.time() - ts > self._ttl:
                # expired
                del self._store[key]
                return None
            return val

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            if len(self._store) >= self._max_size:
                # Evict oldest
                oldest_key = min(self._store.items(), key=lambda kv: kv[1][0])[0]
                self._store.pop(oldest_key, None)
            self._store[key] = (time.time(), value)

    # Convenience sync wrappers
    def get_sync(self, key: str) -> Optional[Any]:
        return asyncio.run(self.get(key))

    def set_sync(self, key: str, value: Any) -> None:
        asyncio.run(self.set(key, value))


# ---------------------------------------------------------------------------
# Embedding Cache (LFU)
# ---------------------------------------------------------------------------


class EmbeddingCache:
    """On-disk LFU cache for text → embedding vector (list[float])."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        workspace = Path(os.environ.get("WORKSPACE_PATH", "/workspace"))
        db_path = db_path or workspace / "data" / "adapters" / "embeddings.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._init_db()
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    key TEXT PRIMARY KEY,
                    vector TEXT NOT NULL,
                    use_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_use_count ON embeddings(use_count)")

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    # Async helpers -------------------------------------------------------
    async def get(self, text: str) -> Optional[Any]:
        key = self._hash(text)
        async with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                cur = conn.execute("SELECT vector, use_count FROM embeddings WHERE key = ?", (key,))
                row = cur.fetchone()
                if row:
                    vector_json, use_count = row
                    conn.execute("UPDATE embeddings SET use_count = ? WHERE key = ?", (use_count + 1, key))
                    return json.loads(vector_json)
        return None

    async def set(self, text: str, vector: Any) -> None:
        key = self._hash(text)
        vector_json = json.dumps(vector, separators=(",", ":"))
        async with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (key, vector, use_count) VALUES (?, ?, COALESCE((SELECT use_count FROM embeddings WHERE key = ?), 0))",
                    (key, vector_json, key),
                )

    # Eviction of least frequently used rows -----------------------------
    async def evict_lfu(self, keep: int = 50000) -> None:
        async with self._lock:
            with sqlite3.connect(self._db_path) as conn:
                cur = conn.execute("SELECT COUNT(*) FROM embeddings")
                total = cur.fetchone()[0]
                if total <= keep:
                    return
                to_delete = total - keep
                conn.execute(
                    "DELETE FROM embeddings WHERE key IN (SELECT key FROM embeddings ORDER BY use_count ASC LIMIT ?)",
                    (to_delete,),
                )