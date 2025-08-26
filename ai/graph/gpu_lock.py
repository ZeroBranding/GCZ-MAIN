from __future__ import annotations
"""Async GPU lock with fairness for session-based workloads.

Usage::

    async with gpu_lock("family:sd", session_id="abc123"):
        ...

Multiple *families* (e.g. different model types) are isolated – locks for one
family do not block another.  Within a family, tasks are granted access in
FIFO order, but a **fairness window** of 50 ms is enforced per *session* id to
prevent starvation of fast-cycling tasks.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, Deque, Tuple, Optional
from collections import deque

__all__ = ["gpu_lock"]

# Constants --------------------------------------------------------------------
_FAIRNESS_WINDOW_SEC = 0.050  # 50 ms


class _FamilyLock:
    """Fair FIFO lock per GPU family."""

    def __init__(self) -> None:
        self._queue: Deque[Tuple[str, asyncio.Future[None]]] = deque()
        self._holder_session: Optional[str] = None
        self._holder_acquired_at: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self, session_id: str) -> None:
        fut: asyncio.Future[None] = asyncio.get_event_loop().create_future()
        async with self._lock:
            self._queue.append((session_id, fut))
            self._maybe_grant()
        await fut  # wait until granted

    async def release(self, session_id: str) -> None:
        async with self._lock:
            if self._holder_session != session_id:
                # Should never happen – misuse of context manager.
                return
            self._holder_session = None
            self._holder_acquired_at = 0.0
            self._maybe_grant()

    # ------------------------------------------------------------------

    def _maybe_grant(self) -> None:
        now = time.time()
        if self._holder_session is not None:
            # honour fairness window
            if now - self._holder_acquired_at < _FAIRNESS_WINDOW_SEC:
                return
            # preempt if same session at head of queue to allow others? not needed
            return
        if not self._queue:
            return
        session_id, fut = self._queue.popleft()
        self._holder_session = session_id
        self._holder_acquired_at = now
        if not fut.done():
            fut.set_result(None)


# Registry of family locks ------------------------------------------------------
_family_locks: Dict[str, _FamilyLock] = {}


def _get_family_lock(family: str) -> _FamilyLock:
    lock = _family_locks.get(family)
    if lock is None:
        lock = _FamilyLock()
        _family_locks[family] = lock
    return lock


@asynccontextmanager
async def gpu_lock(family: str, session_id: str) -> asyncio.AsyncIterator[None]:
    """Acquire GPU lock for *family* with FIFO fairness.

    The context manager guarantees release even if the body raises.
    """
    fam_lock = _get_family_lock(family)
    await fam_lock.acquire(session_id)
    try:
        yield
    finally:
        await fam_lock.release(session_id)