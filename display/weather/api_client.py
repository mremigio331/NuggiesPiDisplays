import logging
import requests

from config import API_BASE as _BASE

logger = logging.getLogger(__name__)


def _req_id(resp: requests.Response) -> str:
    return resp.headers.get("X-Request-ID", "-")


def get_weather() -> dict | None:
    logger.debug("Fetching weather data")
    try:
        resp = requests.get(f"{_BASE}/weather/data", timeout=15)
        resp.raise_for_status()
        logger.debug(f"Weather data ok req_id={_req_id(resp)}")
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch weather data: {e}")
        return None


def get_settings() -> dict | None:
    logger.debug("Fetching weather settings")
    try:
        resp = requests.get(f"{_BASE}/weather/settings", timeout=5)
        resp.raise_for_status()
        logger.debug(f"Weather settings ok req_id={_req_id(resp)}")
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch weather settings: {e}")
        return None


def get_log_level() -> str:
    try:
        resp = requests.get(f"{_BASE}/system/log-level", timeout=3)
        resp.raise_for_status()
        return resp.json().get("log_level", "INFO")
    except requests.RequestException:
        return "INFO"
