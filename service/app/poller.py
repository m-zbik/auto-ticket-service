"""Background poller — the "auto-check for new issues" loop.

Runs as an asyncio task started on app startup. Every POLL_INTERVAL_SECONDS it
syncs open GitHub issues into the DB (see tickets.sync_from_github) so newly
opened issues appear in any UI reading /tickets without that UI polling GitHub
directly (and burning its rate limit).

Exposes a small `state` singleton so /health and /tickets/new can report when the
last poll ran and how many new issues it found.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.config import get_settings
from app.database import async_session_factory
from app.tickets import sync_from_github

logger = logging.getLogger(__name__)


@dataclass
class PollerState:
    last_poll_at: Optional[datetime] = None
    last_new_count: int = 0
    total_discovered: int = 0
    running: bool = False
    _task: Optional[asyncio.Task] = field(default=None, repr=False)


state = PollerState()


async def _poll_once() -> int:
    async with async_session_factory() as session:
        new = await sync_from_github(session)
    state.last_poll_at = datetime.now(timezone.utc)
    state.last_new_count = new
    state.total_discovered += new
    return new


async def _loop() -> None:
    settings = get_settings()
    logger.info("Poller started (every %ss)", settings.poll_interval_seconds)
    state.running = True
    while True:
        try:
            await _poll_once()
        except Exception as e:  # keep the loop alive across transient failures
            logger.warning("Poll iteration failed: %s", e)
        await asyncio.sleep(settings.poll_interval_seconds)


def start() -> None:
    settings = get_settings()
    if not settings.poll_enabled:
        logger.info("Poller disabled (POLL_ENABLED=false)")
        return
    if state._task and not state._task.done():
        return
    state._task = asyncio.create_task(_loop())


async def stop() -> None:
    if state._task:
        state._task.cancel()
        try:
            await state._task
        except asyncio.CancelledError:
            pass
    state.running = False
