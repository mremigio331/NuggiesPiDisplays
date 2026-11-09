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


WS_URL = "ws://localhost:8000/api/text/ws"
FRAME_S = 0.05  # ~20 fps while a row is scrolling or rainbow
IDLE_S = 0.25  # static text only needs to notice overlays and new settings

_settings: dict = {}
_generation = 0  # bumped on every settings change so scrolling restarts
_lock = threading.Lock()


def _update_settings(data: dict):
    global _generation
    with _lock:
        _settings.update(data)
        _generation += 1
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
                logger.warning(f"WebSocket error: {e} - reconnecting in 5s")
                await asyncio.sleep(5)

    asyncio.run(listen())


def run():
    matrix = build_matrix()
    canvas = matrix.CreateFrameCanvas()
    logger.info("Text display starting")
    _apply_log_level()

    initial = api_client.get_settings()
    if initial:
        _update_settings(initial)

    threading.Thread(target=_ws_thread, daemon=True).start()

    seen_generation = -1
    scroll_start = time.monotonic()

    while True:
        # Full-screen overlay (e.g. brightness change) takes over the matrix.
        if overlay_mod.active(canvas):
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(0.25)
            continue

        with _lock:
            row_count = _settings.get("row_count", 1)
            scroll_seconds = _settings.get("scroll_seconds", 2)
            rows = list(_settings.get("rows", []))
            generation = _generation

        now = time.monotonic()
        if generation != seen_generation:
            seen_generation = generation
            scroll_start = now

        animated = renderer.render(
            canvas,
            row_count,
            rows,
            scroll_seconds,
            now - scroll_start,
            (now * 0.25) % 1.0,
        )
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(FRAME_S if animated else IDLE_S)


if __name__ == "__main__":
    run()
