import logging
import requests

from config import API_BASE as _BASE

logger = logging.getLogger(__name__)


def _req_id(resp: requests.Response) -> str:
    return resp.headers.get("X-Request-ID", "-")


def get_settings() -> dict | None:
    logger.debug("Fetching clock settings")
    try:
        resp = requests.get(f"{_BASE}/clock/settings", timeout=5)
        resp.raise_for_status()
        logger.debug(f"Clock settings ok req_id={_req_id(resp)}")
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch clock settings: {e}")
        return None


def get_timers() -> list | None:
    """Saved timers from the API (soonest first), or None if it can't be reached."""
    try:
        resp = requests.get(f"{_BASE}/timers", timeout=3)
        resp.raise_for_status()
        return resp.json().get("timers", [])
    except requests.RequestException as e:
        logger.debug(f"Failed to fetch timers: {e}")
        return None


def get_log_level() -> str:
    try:
        resp = requests.get(f"{_BASE}/system/log-level", timeout=3)
        resp.raise_for_status()
        return resp.json().get("log_level", "INFO")
    except requests.RequestException:
        return "INFO"
