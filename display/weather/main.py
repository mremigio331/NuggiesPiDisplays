"""
Weather display — cycles through four screens:
  1. Current conditions (temp, icon, feels-like, city, wind)
  2. Hourly forecast   (next 6 hours)
  3. 5-day forecast    (high / low)
  4. Sky               (sun by day, moon by night, over the mountains)

Website controls (both live in the weather settings):
  force_view   one-shot "Show now": jump to a screen once, then keep rotating.
  locked_view  "Lock": stay on one screen until unlocked, or until the user
               picks another display by hand (survives restarts).
"""

import os, sys

try:
    os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(90))
except Exception:
    pass  # not root or unsupported
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import time

import api_client
import renderer
import overlay as overlay_mod
from matrix import build_matrix

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

SCREENS = ("current", "hourly", "forecast", "sky")


def _lock_of(settings: dict) -> str | None:
    lv = (settings.get("locked_view") or "").strip()
    return lv if lv in SCREENS else None


def _poll() -> tuple[str | None, str | None]:
    """One settings read. Returns (pending show-now screen, current lock).
    A show-now request is consumed (cleared) as soon as it is seen."""
    settings = api_client.get_settings() or {}
    forced = (settings.get("force_view") or "").strip() or None
    if forced:
        api_client.clear_force_view()  # consume once, even if the name is unknown
        if forced not in SCREENS:
            forced = None
    return forced, _lock_of(settings)


def _draw(name: str, canvas, data: dict) -> bool:
    """Render one screen. False means it has nothing to show right now."""
    if name == "current":
        renderer.render_current(canvas, data)
        return True
    if name == "hourly":
        if not data.get("hourly"):
            return False
        renderer.render_hourly(canvas, data)
        return True
    if name == "forecast":
        if not data.get("daily"):
            return False
        renderer.render_forecast(canvas, data)
        return True
    if name == "sky":
        return renderer.render_sky(canvas, data)
    return False


def _dwell(matrix, canvas, seconds: float, name: str, data: dict, lock: str | None):
    """Hold screen *name* for up to *seconds*.

    - Renders the factory-reset overlay promptly if it appears (~every 0.5s).
    - Redraws the screen when the minute changes, so on-screen clocks and the
      sun/moon stay current even on a long or locked dwell.
    - About once a second, checks for a show-now request or a lock change.

    Returns (canvas, next_screen, lock_changed):
      next_screen   a show-now target to jump to (ignored while locked)
      lock_changed  True when the lock was set, cleared or moved
    """
    deadline = time.time() + seconds
    minute = time.localtime().tm_min
    tick = 0
    while time.time() < deadline:
        if overlay_mod.active(canvas):
            canvas = matrix.SwapOnVSync(canvas)
        if tick % 2 == 0:
            forced, new_lock = _poll()
            if new_lock != lock:
                return canvas, None, True
            if forced and not lock:
                return canvas, forced, False
            now_min = time.localtime().tm_min
            if now_min != minute:
                minute = now_min
                if _draw(name, canvas, data):
                    canvas = matrix.SwapOnVSync(canvas)
        tick += 1
        time.sleep(0.5)
    return canvas, None, False


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
    api_client.clear_force_view()  # drop a stale request left from before start

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
        lock = _lock_of(settings)

        # ── Locked: stay on one screen. Loop back every dwell so the weather
        #    data still refreshes. If the locked screen has nothing to show
        #    (e.g. no sun times), fall through to the normal rotation.
        if lock and _draw(lock, canvas, data):
            logger.info(f"Locked on {lock} ({t}s)")
            canvas = matrix.SwapOnVSync(canvas)
            canvas, _, _ = _dwell(matrix, canvas, t, lock, data, lock)
            continue

        # ── Rotation. A show-now jumps straight to its screen; rotation then
        #    carries on with the screen after the one it interrupted. A lock
        #    change restarts the loop so it takes effect within a second.
        lock_changed = False
        for name in SCREENS:
            pending: str | None = name
            while pending:
                if not _draw(pending, canvas, data):
                    break
                logger.info(f"Showing {pending} ({t}s)")
                canvas = matrix.SwapOnVSync(canvas)
                canvas, nxt, lock_changed = _dwell(
                    matrix, canvas, t, pending, data, lock
                )
                pending = nxt
                if lock_changed:
                    break
            if lock_changed:
                break


if __name__ == "__main__":
    run()
