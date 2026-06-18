import logging
import requests
from config import API_BASE as _BASE

logger = logging.getLogger(__name__)


def _get(path: str, timeout: int = 10) -> dict | None:
    try:
        resp = requests.get(f"{_BASE}{path}", timeout=timeout)
        resp.raise_for_status()
        logger.debug(f"GET {path} ok req_id={resp.headers.get('X-Request-ID', '-')}")
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"GET {path} failed: {e}")
        return None


def get_nba_scoreboard() -> dict | None:
    return _get("/sports/nba/scoreboard")


def get_nba_game_details(event_id: str) -> dict | None:
    return _get(f"/sports/nba/game/{event_id}")


def get_mlb_scoreboard() -> dict | None:
    return _get("/sports/mlb/scoreboard")


def get_mlb_game_details(event_id: str) -> dict | None:
    return _get(f"/sports/mlb/game/{event_id}")


def get_nhl_scoreboard() -> dict | None:
    return _get("/sports/nhl/scoreboard")


def get_nhl_game_details(event_id: str) -> dict | None:
    return _get(f"/sports/nhl/game/{event_id}")


def get_soccer_scoreboard(league: str = "fifa.world") -> dict | None:
    return _get(f"/sports/soccer/scoreboard?league={league}")


def get_soccer_game_details(event_id: str, league: str = "fifa.world") -> dict | None:
    return _get(f"/sports/soccer/game/{event_id}?league={league}")


def get_settings() -> dict | None:
    return _get("/sports/settings", timeout=5)


def get_log_level() -> str:
    result = _get("/system/log-level", timeout=3)
    return (result or {}).get("log_level", "INFO")
