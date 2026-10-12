import os, sys

try:
    os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(90))
except Exception:
    pass  # not root or unsupported
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import websockets
import api_client
import renderer
import overlay as overlay_mod
from matrix import build_matrix

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _apply_log_level() -> None:
    level = api_client.get_log_level()
    logging.getLogger().setLevel(getattr(logging, level, logging.INFO))
    logger.debug(f"Log level applied: {level}")


WS_URL = "ws://localhost:8000/api/clock/ws"

_settings: dict = {}
_lock = threading.Lock()


def _update_settings(data: dict):
    with _lock:
        _settings.update(data)
    logger.info(f"Settings updated: {list(data.keys())}")


def _ws_thread():
    async def listen():
        while True:
            try:
                async with websockets.connect(WS_URL) as ws:
                    logger.info("WebSocket connected")
                    async for message in ws:
                        _update_settings(json.loads(message))
            except Exception as e:
                logger.warning(f"WebSocket error: {e} — reconnecting in 5s")
                await asyncio.sleep(5)

    asyncio.run(listen())


def run():
    matrix = build_matrix()
    canvas = matrix.CreateFrameCanvas()
    logger.info("Clock display starting")
    _apply_log_level()

    initial = api_client.get_settings()
    if initial:
        _update_settings(initial)

    threading.Thread(target=_ws_thread, daemon=True).start()

    # The display goes down the `timezones` list. In focus mode it advances one
    # zone per step; in multi mode it advances one page (of three) per step.
    # A step lasts `cycle_seconds`.
    step_index = 0
    last_step_flip = time.monotonic()

    while True:
        # Full-screen overlay (factory-reset countdown / "Factory Reset") takes
        # over the whole matrix regardless of display mode.
        if overlay_mod.active(canvas):
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(0.25)
            continue

        with _lock:
            zones = list(_settings.get("timezones", []))
            display_mode = _settings.get("display_mode", "focus")
            cycle_seconds = _settings.get("cycle_seconds", 5)
            color = tuple(_settings.get("color", [255, 255, 255]))
            color_mode = _settings.get("color_mode", "solid")
            use_24h = _settings.get("use_24h", False)

        rainbow = color_mode == "rainbow"

        if not zones:
            zones = ["UTC"]
        try:
            cycle_seconds = max(1, int(cycle_seconds))
        except (TypeError, ValueError):
            cycle_seconds = 5

        # Build the list of steps for the current mode. In focus mode each step
        # is a single zone; in multi mode each step is a slice of up to three.
        if display_mode == "multi":
            steps = [zones[i : i + 3] for i in range(0, len(zones), 3)]
        else:
            steps = [[z] for z in zones]
        if not steps:
            steps = [["UTC"]]

        # Advance the step on the cycle timer, wrapping around the list.
        now = time.monotonic()
        if now - last_step_flip >= cycle_seconds:
            step_index += 1
            last_step_flip = now
        if step_index >= len(steps):
            step_index = 0
        current_zones = steps[step_index]

        # Rainbow phase advances with wall-clock time so hues slide right at a
        # steady rate regardless of frame timing. One full cycle ~every 4s.
        phase = (now * 0.25) % 1.0 if rainbow else None

        if display_mode == "multi":
            renderer.render_multi(
                canvas, _entries_for(current_zones), color, use_24h, phase
            )
        else:
            tz_name = current_zones[0]
            try:
                tz = ZoneInfo(tz_name)
            except Exception:
                tz_name, tz = "UTC", ZoneInfo("UTC")
            renderer.render(canvas, datetime.now(tz), color, use_24h, tz_name, phase)

        canvas = matrix.SwapOnVSync(canvas)
        # Animate smoothly in rainbow mode; otherwise the clock only needs a
        # once-per-second tick.
        time.sleep(1 / 15 if rainbow else 1)


def _entries_for(zone_names: list) -> list:
    """Return (abbr, datetime) tuples for each valid zone, in list order."""
    entries = []
    for name in zone_names:
        try:
            tz = ZoneInfo(name)
        except Exception:
            continue
        dt = datetime.now(tz)
        abbr = dt.strftime("%Z")
        if not abbr or any(ch.isdigit() for ch in abbr):
            abbr = name.split("/")[-1][:4].upper()
        entries.append((abbr, dt))
    return entries


if __name__ == "__main__":
    run()
