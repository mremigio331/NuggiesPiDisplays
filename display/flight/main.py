"""
Flight display: the closest plane in the sky to the user's saved spot.

The API owns the data: it calls the free ADS-B feeds at most once a minute
and caches the answer. This loop just asks the API every POLL_SECONDS (cheap,
local), so a new spot saved on the website shows within seconds, and redraws
when the answer changes. Airline logos come from the API (it downloads each
one once) and are kept in memory here.
"""

import os, sys

try:
    os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(90))
except Exception:
    pass  # not root or unsupported
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
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

POLL_SECONDS = 10
TICK_SECONDS = 0.5  # how often the factory-reset / timer overlay is checked


def _apply_log_level() -> None:
    level = api_client.get_log_level()
    logging.getLogger().setLevel(getattr(logging, level, logging.INFO))


def _view_key(data: dict | None) -> str:
    """What is on screen, so the panel only redraws when it would change."""
    if data is None:
        return "none"
    return json.dumps(
        {
            "configured": data.get("configured"),
            "has_data": data.get("aircraft") is not None,
            "closest": data.get("closest"),
            "radius": data.get("radius"),
            "units": data.get("units"),
            "airlines_only": data.get("airlines_only"),
        },
        sort_keys=True,
        default=str,
    )


LOGO_RETRY_SECONDS = 10 * 60
_logos: dict[str, tuple] = {}  # IATA code -> (16x16 image or None, monotonic time)


def _logo_for(plane: dict):
    """The plane's airline logo, fetched once per airline. A miss is retried
    after LOGO_RETRY_SECONDS."""
    airline = plane.get("airline") if isinstance(plane.get("airline"), dict) else None
    code = (airline or {}).get("iata")
    if not code:
        return None
    img, at = _logos.get(code, (None, None))
    if at is None or (img is None and time.monotonic() - at > LOGO_RETRY_SECONDS):
        img = api_client.get_logo(code)
        _logos[code] = (img, time.monotonic())
    return img


def run() -> None:
    matrix = build_matrix()
    canvas = matrix.CreateFrameCanvas()
    logger.info("Flight display starting")
    _apply_log_level()

    renderer.render_loading(canvas)
    canvas = matrix.SwapOnVSync(canvas)

    data = None
    shown = None  # _view_key of what is on the panel; None forces a redraw
    last_poll = 0.0
    logged = None  # (screen, callsign) last written to the log

    while True:
        if overlay_mod.active(canvas):
            canvas = matrix.SwapOnVSync(canvas)
            shown = None  # repaint the plane once the overlay goes away
            time.sleep(TICK_SECONDS)
            continue

        now = time.monotonic()
        if now - last_poll >= POLL_SECONDS:
            last_poll = now
            data = api_client.get_nearby()

        closest = (data or {}).get("closest") or {}
        logo = _logo_for(closest)
        # Start airport, end airport, aircraft, distance flown: PHASE_SECONDS each.
        phase = int(time.time() // renderer.PHASE_SECONDS) % renderer.phase_count(data)
        key = _view_key(data) + f"|{phase}|{logo is not None}"
        if key != shown:
            screen = renderer.render(canvas, data, phase, logo)
            canvas = matrix.SwapOnVSync(canvas)
            shown = key
            who = closest.get("callsign") or closest.get("hex") or ""
            if (screen, who) != logged:
                logged = (screen, who)
                logger.info(f"Showing {screen}" + (f": {who}" if who else ""))

        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    run()
