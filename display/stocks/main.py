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


def _apply_log_level() -> None:
    level = api_client.get_log_level()
    logging.getLogger().setLevel(getattr(logging, level, logging.INFO))
    logger.debug(f"Log level applied: {level}")


DEFAULT_INTERVAL = 60
CYCLE_SECONDS = 5


def _build_queue(settings: dict) -> list[dict]:
    symbols = settings.get("stock_abbrs", [])
    cycles = [c for c in settings.get("stock_cycles", []) if c.get("enabled")]
    return [{"symbol": s, "cycle_key": c["key"]} for s in symbols for c in cycles]


def _parse_force(settings: dict):
    """Return (symbol, cycle_key) from a 'SYMBOL:cycle_key' force_view, or None."""
    fv = (settings.get("force_view") or "").strip()
    if not fv or ":" not in fv:
        return None
    symbol, _, cycle_key = fv.partition(":")
    symbol, cycle_key = symbol.strip().upper(), cycle_key.strip()
    if not symbol or not cycle_key:
        return None
    return symbol, cycle_key


# Tracks the last-consumed force_view string, shared between the main loop and
# the dwell loop so a "show now" fires exactly once.
_force = {"last": ""}


def _poll_new_force():
    """If a new (not-yet-consumed) force_view is set, consume and return it as
    (symbol, cycle_key); otherwise None. Cheap enough to call ~1x/sec."""
    settings = api_client.get_settings() or {}
    fv_raw = (settings.get("force_view") or "").strip()
    if not fv_raw or fv_raw == _force["last"]:
        return None
    parsed = _parse_force(settings)
    if parsed is None:
        return None
    _force["last"] = fv_raw  # consume once
    return parsed


def _display_item(matrix, canvas, data: dict, interval: int):
    """Hold one chart for `interval` seconds, alternating price/percent every
    CYCLE_SECONDS. Polls for a "show now" request each second and returns early
    (with the pending jump) so the display reacts promptly.

    Returns (canvas, pending_force) where pending_force is (symbol, cycle_key)
    if a jump was requested mid-dwell, else None."""
    start = time.time()
    show_pct = True
    last_swap = 0.0
    while time.time() - start < interval:
        # Factory-reset overlay takes over the whole matrix.
        if overlay_mod.active(canvas):
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(0.5)
            continue
        # Re-render only every CYCLE_SECONDS, but wake once a second to stay
        # responsive to a "show now" request.
        if time.time() - last_swap >= CYCLE_SECONDS:
            renderer.render(canvas, data, show_pct=show_pct)
            canvas = matrix.SwapOnVSync(canvas)
            show_pct = not show_pct
            last_swap = time.time()
        pending = _poll_new_force()
        if pending is not None:
            return canvas, pending
        time.sleep(1)
    return canvas, None


def _show(matrix, canvas, symbol: str, cycle_key: str, interval: int):
    """Fetch and display one ticker/cycle for up to `interval` seconds.

    Returns (canvas, pending_force). pending_force is a requested jump that
    interrupted the dwell (or None). If the chart can't be fetched, returns
    (canvas, None) without changing the screen."""
    logger.info(f"Fetching {symbol}/{cycle_key}")
    data = api_client.get_stock_chart(symbol, cycle_key)
    if data is None:
        logger.warning(f"No data for {symbol}/{cycle_key}, skipping")
        return canvas, None
    api_client.set_current(symbol, cycle_key)
    logger.info(f"Showing {symbol}/{cycle_key} for up to {interval}s")
    return _display_item(matrix, canvas, data, interval)


def run():
    matrix = build_matrix()
    canvas = matrix.CreateFrameCanvas()
    logger.info("Stocks display starting")
    _apply_log_level()

    # "Show now": the website sets force_view to "SYMBOL:cycle_key". Seed the
    # consumed marker from the current value so a stale force left in settings
    # doesn't trigger a spurious jump on startup.
    seed = api_client.get_settings() or {}
    _force["last"] = (seed.get("force_view") or "").strip()

    while True:
        settings = api_client.get_settings() or {}
        queue = _build_queue(settings)
        interval = settings.get("interval_seconds", DEFAULT_INTERVAL)

        if not queue:
            logger.warning("No stocks/cycles configured, retrying in 30s")
            time.sleep(30)
            continue

        for item in queue:
            symbol, cycle_key = item["symbol"], item["cycle_key"]
            canvas, pending = _show(matrix, canvas, symbol, cycle_key, interval)
            # A "show now" request can interrupt the dwell, and each forced view
            # can itself be interrupted by the next request — keep servicing
            # jumps until the dwell completes without one.
            while pending is not None:
                logger.info(f"Jumping to requested view {pending[0]}:{pending[1]}")
                canvas, pending = _show(
                    matrix, canvas, pending[0], pending[1], interval
                )


if __name__ == "__main__":
    run()
