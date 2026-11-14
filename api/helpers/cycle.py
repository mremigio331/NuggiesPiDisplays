"""Rotates the display through the active saved cycle.

Runs as a background task in the API lifespan. A cycle is not a display mode:
it switches real modes, so active_display and the website stay accurate. Manual
switches, the board buttons and schedule mode rules all stop the cycle. While
the display is powered off the cycle waits, then gives the view its full time.
"""

import asyncio
import logging
import time

from helpers.config import (
    active_cycle,
    cycle_steps,
    read_settings,
    write_settings,
)
from helpers.process import start_display, is_running
from helpers.schedule import _apply_option
from helpers.wifi_state import WIFI_FLAG

logger = logging.getLogger(__name__)

TICK_SECONDS = 5

_signature: tuple | None = None  # what's rotating; any edit restarts the cycle
_index = 0
_next_at: float | None = None


def _show(step: tuple) -> None:
    mode, option = step
    _apply_option(mode, option)
    start_display(mode)
    settings = read_settings()
    settings["active_display"] = mode
    write_settings(settings)
    logger.info("Cycle: showing %r%s", mode, f" ({option})" if option else "")


def _tick() -> None:
    global _signature, _index, _next_at

    cycle = active_cycle()
    if cycle is None:
        _signature = None
        _next_at = None
        return
    if not is_running():
        _next_at = None
        return

    steps = cycle_steps(cycle)
    if not steps:
        return
    seconds = cycle["minutes"] * 60
    now = time.monotonic()
    signature = (cycle["id"], seconds, tuple(steps))

    if signature != _signature:
        _show(steps[0])
        _signature, _index, _next_at = signature, 0, now + seconds
    elif _next_at is None:
        _next_at = now + seconds
    elif now >= _next_at:
        index = (_index + 1) % len(steps)
        _show(steps[index])
        _index, _next_at = index, now + seconds


async def run_cycler() -> None:
    logger.info("Display cycler started (tick %ss)", TICK_SECONDS)
    while True:
        try:
            # WiFi-setup mode owns the panel (mirrors the scheduler's guard).
            if WIFI_FLAG.exists():
                _tick()
        except Exception:
            logger.exception("Display cycler tick crashed (continuing)")
        await asyncio.sleep(TICK_SECONDS)
