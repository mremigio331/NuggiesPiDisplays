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


WS_URL = "ws://localhost:8000/clock/ws"

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

    while True:
        with _lock:
            tz_name = _settings.get("timezone", "UTC")
            color = tuple(_settings.get("color", [255, 255, 255]))
            use_24h = _settings.get("use_24h", False)

        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("UTC")

        current = datetime.now(tz)
        renderer.render(canvas, current, color, use_24h)
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(1)


if __name__ == "__main__":
    run()
