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
from matrix import build_matrix

_DEBUG_DIR = Path("/var/log/nuggies")
_DEBUG_FILE = _DEBUG_DIR / "mlb_debug.json"
_STATE_FILE = _DEBUG_DIR / "sports_now.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

SCOREBOARD_REFRESH = 60  # re-fetch scoreboard when no live game
LIVE_REFRESH = 30  # re-fetch scoreboard when a game is live
DETAILS_TTL = 15  # re-fetch game details (players/fouls)
PANEL_CYCLE = 15  # seconds between stat views (focus mode)
OVERVIEW_CYCLE = 20  # seconds per game pair (overview mode)
_CYCLES_PER_GAME = 2  # full stat cycles before advancing to next game (focus mode)

_NBA_PANEL_VIEWS = ["pts", "ast", "reb", "fouls"]
_MLB_POST_VIEWS = ["hits", "rbi"]
_NHL_PANEL_VIEWS = ["stats", "goals", "away_ice", "home_ice"]
_SOCCER_PANEL_VIEWS = ["stats", "goals"]

# Adding a new sport: add one entry here + ESPN client methods + API endpoints.
_SPORT_CONFIG: dict[str, dict] = {
    "nba": {
        "label": "NBA",
        "fetch_scoreboard": api_client.get_nba_scoreboard,
        "fetch_details": api_client.get_nba_game_details,
        "panel_views": _NBA_PANEL_VIEWS,
        "live_details": True,  # fetch detail endpoint for live games (stat leaders)
        "render_focus": renderer.render_game,
        "render_overview": renderer.render_game_overview,
    },
    "mlb": {
        "label": "MLB",
        "fetch_scoreboard": api_client.get_mlb_scoreboard,
        "fetch_details": api_client.get_mlb_game_details,
        "panel_views": _MLB_POST_VIEWS,
        "live_details": True,  # fetch details for live games to get last_pitch from plays
        "render_focus": renderer.render_baseball_game,
        "render_overview": renderer.render_baseball_overview,
    },
    "nhl": {
        "label": "NHL",
        "fetch_scoreboard": api_client.get_nhl_scoreboard,
        "fetch_details": api_client.get_nhl_game_details,
        "panel_views": _NHL_PANEL_VIEWS,
        "live_details": True,
        "render_focus": renderer.render_hockey_game,
        "render_overview": renderer.render_hockey_overview,
    },
    "soccer": {
        "label": "Soccer",
        "fetch_scoreboard": None,  # resolved dynamically based on league setting
        "fetch_details": None,
        "panel_views": _SOCCER_PANEL_VIEWS,
        "live_details": True,
        "render_focus": renderer.render_soccer_game,
        "render_overview": renderer.render_soccer_overview,
    },
}


def _write_state(sport: str, display_mode: str, event_ids: list[str]) -> None:
    try:
        _DEBUG_DIR.mkdir(exist_ok=True)
        _STATE_FILE.write_text(
            json.dumps(
                {
                    "sport": sport,
                    "display_mode": display_mode,
                    "active_event_ids": [e for e in event_ids if e],
                }
            )
        )
    except Exception:
        pass


def _apply_log_level() -> None:
    level = api_client.get_log_level()
    logging.getLogger().setLevel(getattr(logging, level, logging.INFO))


def _has_live_game(games: list[dict]) -> bool:
    return any(g.get("state") == "in" for g in games)


def run() -> None:
    matrix = build_matrix()
    canvas = matrix.CreateFrameCanvas()
    logger.info("Sports display starting")
    _apply_log_level()

    games: list[dict] = []
    details_cache: dict[str, tuple[float, dict | None]] = {}
    _debug_dumped: set[str] = set()  # event_ids already written to debug file

    last_scoreboard_fetch = 0.0
    last_panel_flip = 0.0
    last_game_flip = 0.0
    game_idx = 0
    panel_idx = 0
    panel_flip_count = 0
    active_sport: str = ""  # tracks last seen sport to detect changes

    while True:
        now = time.time()
        settings = api_client.get_settings() or {}
        sport = settings.get("sport", "nba")
        cfg = _SPORT_CONFIG.get(sport, _SPORT_CONFIG["nba"])

        # Reset on sport change so we fetch the new league immediately
        if sport != active_sport:
            logger.info(f"Sport changed: {active_sport!r} → {sport!r}")
            active_sport = sport
            games = []
            last_scoreboard_fetch = 0.0
            game_idx = 0
            panel_idx = 0
            panel_flip_count = 0
            details_cache.clear()

        # For soccer, resolve league-specific fetch functions
        if sport == "soccer":
            soccer_league = settings.get("soccer_league", "fifa.world")
            fetch_scoreboard = lambda: api_client.get_soccer_scoreboard(soccer_league)
            fetch_details = lambda eid: api_client.get_soccer_game_details(
                eid, soccer_league
            )
        else:
            fetch_scoreboard = cfg["fetch_scoreboard"]
            fetch_details = cfg["fetch_details"]

        # Refresh scoreboard
        refresh_interval = LIVE_REFRESH if _has_live_game(games) else SCOREBOARD_REFRESH
        if (now - last_scoreboard_fetch) >= refresh_interval:
            logger.info(f"Fetching {cfg['label']} scoreboard…")
            fresh = fetch_scoreboard()
            if fresh is not None:
                games = fresh.get("games", [])
                last_scoreboard_fetch = now
                logger.info(f"Scoreboard updated: {len(games)} games")
            elif not games:
                logger.warning("No scoreboard data, retrying in 30s")
                renderer.render_no_games(canvas, cfg["label"])
                canvas = matrix.SwapOnVSync(canvas)
                time.sleep(30)
                continue

        if not games:
            renderer.render_no_games(canvas, cfg["label"])
            canvas = matrix.SwapOnVSync(canvas)
            time.sleep(1)
            continue

        display_mode = settings.get("display_mode", "focus")

        if display_mode == "overview":
            # Advance by 2 each cycle (two games shown at once)
            if (now - last_game_flip) >= OVERVIEW_CYCLE:
                if last_game_flip > 0:
                    game_idx = (game_idx + 2) % max(len(games), 1)
                last_game_flip = now

            game_a = games[game_idx % len(games)]
            game_b = games[(game_idx + 1) % len(games)] if len(games) > 1 else None
            logger.debug(
                f"{cfg['label']} overview {game_idx + 1}/{len(games)}: "
                f"{game_a.get('away_team')} @ {game_a.get('home_team')} [{game_a.get('state')}]"
            )
            _write_state(
                sport,
                display_mode,
                [
                    game_a.get("event_id", ""),
                    *(([game_b.get("event_id", "")] if game_b else [])),
                ],
            )
            cfg["render_overview"](canvas, game_a, game_b)

        else:  # focus
            panel_views = cfg["panel_views"]

            # Sports without live detail endpoints (e.g. MLB) skip panel cycling when live
            game = games[game_idx % len(games)]
            skip_cycle = not cfg["live_details"] and game.get("state") == "in"

            if not skip_cycle:
                if (now - last_panel_flip) >= PANEL_CYCLE:
                    if last_panel_flip > 0:
                        panel_idx = (panel_idx + 1) % len(panel_views)
                        panel_flip_count += 1
                        if panel_flip_count >= len(panel_views) * _CYCLES_PER_GAME:
                            game_idx = (game_idx + 1) % max(len(games), 1)
                            panel_flip_count = 0
                    last_panel_flip = now

            game = games[game_idx % len(games)]
            event_id = game.get("event_id", "")
            state = game.get("state", "pre")

            details: dict | None = None
            should_fetch_details = event_id and (
                state == "post" or (cfg["live_details"] and state == "in")
            )
            if should_fetch_details:
                cached = details_cache.get(event_id)
                if not cached or (now - cached[0]) >= DETAILS_TTL:
                    logger.debug(
                        f"Fetching {cfg['label']} game details for {event_id}…"
                    )
                    details = fetch_details(event_id)
                    details_cache[event_id] = (now, details)
                    # Dump raw data to file once per event for debugging
                    if event_id not in _debug_dumped:
                        _debug_dumped.add(event_id)
                        try:
                            _DEBUG_DIR.mkdir(exist_ok=True)
                            payload = {"game": game, "details": details}
                            _DEBUG_FILE.write_text(json.dumps(payload, indent=2))
                            logger.info(f"Debug dump written to {_DEBUG_FILE}")
                        except Exception as exc:
                            logger.warning(f"Debug dump failed: {exc}")
                else:
                    details = cached[1]

            panel_view = (
                "live" if skip_cycle else panel_views[panel_idx % len(panel_views)]
            )
            logger.debug(
                f"{cfg['label']} focus {game_idx + 1}/{len(games)}: "
                f"{game.get('away_team')} @ {game.get('home_team')} "
                f"[{state}] panel={panel_view}"
            )
            _write_state(sport, display_mode, [game.get("event_id", "")])
            cfg["render_focus"](canvas, game, details, panel_view)

        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(1)


if __name__ == "__main__":
    run()
