"""
Weather display — cycles through three screens:
  1. Current conditions (temp, icon, feels-like, city, wind)
  2. Hourly forecast   (next 6 hours)
  3. 5-day forecast    (high / low)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import time

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


DEFAULT_CYCLE_DURATION = 60
REFRESH_INTERVAL = 30 * 60  # re-fetch weather every 30 minutes


def run() -> None:
    matrix = build_matrix()
    canvas = matrix.CreateFrameCanvas()
    logger.info("Weather display starting")
    _apply_log_level()

    data: dict | None = None
    last_fetch = 0.0

    while True:
        now = time.time()

        # Refresh weather data periodically
        if data is None or (now - last_fetch) >= REFRESH_INTERVAL:
            logger.info("Fetching weather data…")
            fresh = api_client.get_weather()
            if fresh and "current" in fresh:
                data = fresh
                last_fetch = now
                logger.info("Weather data updated")
            elif data is None:
                logger.warning("No weather data yet, retrying in 30s")
                time.sleep(30)
                continue

        settings = api_client.get_settings() or {}
        t = settings.get("cycle_duration", DEFAULT_CYCLE_DURATION)

        # ── Screen 1: current conditions ──────────────────────────────────
        logger.info(f"Showing current conditions ({t}s)")
        renderer.render_current(canvas, data)
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(t)

        # ── Screen 2: hourly forecast ─────────────────────────────────────
        if data.get("hourly"):
            logger.info(f"Showing hourly forecast ({t}s)")
            renderer.render_hourly(canvas, data)
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(t)

        # ── Screen 3: 5-day forecast ──────────────────────────────────────
        if data.get("daily"):
            logger.info(f"Showing 5-day forecast ({t}s)")
            renderer.render_forecast(canvas, data)
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(t)


if __name__ == "__main__":
    run()
