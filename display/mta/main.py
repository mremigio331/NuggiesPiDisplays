import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import random
import time
import api_client
import renderer
from matrix import build_matrix
from renderer import WIN_ARRIVING, WIN_WAITING

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _apply_log_level() -> None:
    level = api_client.get_log_level()
    logging.getLogger().setLevel(getattr(logging, level, logging.INFO))
    logger.debug(f"Log level applied: {level}")


FETCH_INTERVAL = 30  # seconds between successful fetches
RETRY_INTERVAL = 5  # seconds between retries when API is down
SETTINGS_INTERVAL = 60  # seconds between re-reading cycle settings
STATION_LOAD_S = 15  # seconds to show the loading graphic after a station change
PAIR_SECONDS = 35  # seconds per train pair (matches original 35-frame loop)
DEST_SCROLL_S = 2.0  # seconds per character scroll step
SCROLL_STEP_S = (
    0.5  # seconds per station-name scroll pixel (matches 4px/2s dest scroll)
)
LOGO_REFRESH_S = 2.0  # seconds between random line picks on error screen
FRAME_S = 0.05  # ~20 fps

_ALL_LINES = [
    "A",
    "C",
    "E",
    "B",
    "D",
    "F",
    "M",
    "G",
    "J",
    "Z",
    "L",
    "N",
    "Q",
    "R",
    "W",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
]


def _random_lines(n: int = 6) -> list:
    return random.sample(_ALL_LINES, min(n, len(_ALL_LINES)))


def _advance_dest_scroll(offsets: list, pair: list) -> list:
    result = list(offsets)
    for i, train in enumerate(pair[:2]):
        dest = train.get("destination", "")
        mins = train.get("arrival_minutes", "")
        window = WIN_ARRIVING if mins == 0 else WIN_WAITING
        if len(dest) > window:
            result[i] += 1
            if result[i] >= len(dest):
                result[i] = 0
    return result


def _load_cycle_settings() -> tuple[bool, int]:
    """Return (cycle_enabled, cycle_seconds). Falls back to disabled on error."""
    settings = api_client.get_mta_settings()
    if not settings:
        logger.warning("Could not read MTA settings; cycle disabled until next read")
        return False, 0
    mta = settings.get("mta", settings)
    enabled = str(mta.get("cycle", "false")).lower() in ("true", "1", "yes")
    try:
        seconds = int(mta.get("cycle_time", 300))
    except (ValueError, TypeError):
        seconds = 300
    logger.info(f"Cycle settings loaded: enabled={enabled} every {seconds} sec")
    return enabled, seconds


def _cycle_station(current_station: str) -> str:
    """Pick a different enabled station, tell the API, return the new name (or current on failure)."""
    stations = api_client.get_enabled_stations()
    if not stations:
        logger.warning("Could not fetch enabled stations; keeping current station")
        return current_station
    candidates = [s for s in stations if s != current_station]
    new_station = random.choice(candidates if candidates else stations)
    if api_client.set_station(new_station):
        logger.info(
            f"Cycle: changed station from '{current_station}' to '{new_station}'"
        )
        return new_station
    else:
        logger.warning(
            f"Failed to set station to '{new_station}'; keeping '{current_station}'"
        )
        return current_station


def run():
    matrix = build_matrix()
    canvas = matrix.CreateFrameCanvas()
    logger.info("MTA display starting")
    _apply_log_level()

    trains = []
    station_name = ""
    station_scroll_x = 0
    dest_char_offsets = [0, 0]
    show_first = True
    api_error = False
    loading_lines = _random_lines()

    last_fetch = 0.0
    last_settings_read = 0.0
    last_cycle = time.time()
    last_pair_switch = time.time()
    last_station_scroll = time.time()
    last_dest_scroll = time.time()
    last_logo_refresh = time.time()
    station_changed_at = time.time()  # show loading graphic on startup

    cycle_enabled, cycle_seconds = _load_cycle_settings()
    last_settings_read = time.time()

    while True:
        now = time.time()

        # Re-read cycle settings periodically
        if now - last_settings_read >= SETTINGS_INTERVAL:
            cycle_enabled, cycle_seconds = _load_cycle_settings()
            last_settings_read = now

        # Station cycling
        if cycle_enabled and cycle_seconds > 0 and now - last_cycle >= cycle_seconds:
            new_name = _cycle_station(station_name)
            if new_name != station_name:
                station_name = new_name
                station_changed_at = now
                last_fetch = 0.0  # force immediate re-fetch
            last_cycle = now

        # Fetch trains from API
        interval = RETRY_INTERVAL if api_error else FETCH_INTERVAL
        if now - last_fetch >= interval:
            data = api_client.get_next_four()
            if data:
                if api_error:
                    logger.info("API recovered")
                api_error = False
                trains = data.get("trains", [])
                new_name = data.get("stop_name") or data.get("station", "")
                if new_name != station_name:
                    logger.info(f"Station set to '{new_name}'")
                    station_name = new_name
                    station_scroll_x = 0
                    dest_char_offsets = [0, 0]
                    station_changed_at = now
                logger.info(f"Fetched {len(trains)} trains for '{station_name}'")
            else:
                if not api_error:
                    logger.warning("API unreachable, showing error state")
                api_error = True
            last_fetch = now

        show_loading = not api_error and (now - station_changed_at < STATION_LOAD_S)

        # Refresh random logo lines during error or station-change loading
        if (api_error or show_loading) and now - last_logo_refresh >= LOGO_REFRESH_S:
            loading_lines = _random_lines()
            last_logo_refresh = now

        # Switch between train pair 1 (0-1) and pair 2 (2-3)
        if now - last_pair_switch >= PAIR_SECONDS:
            show_first = not show_first
            dest_char_offsets = [0, 0]
            last_pair_switch = now

        # Advance station name scroll
        if now - last_station_scroll >= SCROLL_STEP_S:
            station_scroll_x += 1
            last_station_scroll = now

        # Advance destination character scroll
        pair = trains[:2] if show_first else trains[2:4]
        if not api_error and now - last_dest_scroll >= DEST_SCROLL_S:
            dest_char_offsets = _advance_dest_scroll(dest_char_offsets, pair)
            last_dest_scroll = now

        renderer.render(
            canvas,
            station_name,
            pair,
            station_scroll_x=station_scroll_x,
            dest_char_offsets=dest_char_offsets,
            api_error=api_error,
            show_loading=show_loading,
            loading_lines=loading_lines,
        )
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(FRAME_S)


if __name__ == "__main__":
    run()
