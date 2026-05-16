import logging
import requests

from config import API_BASE as _BASE

logger = logging.getLogger(__name__)


def _req_id(resp: requests.Response) -> str:
    return resp.headers.get("X-Request-ID", "-")


def get_stock_chart(symbol: str, cycle_key: str) -> dict | None:
    logger.debug(f"Fetching chart {symbol}/{cycle_key}")
    try:
        resp = requests.get(f"{_BASE}/stonks/{symbol}/{cycle_key}", timeout=10)
        resp.raise_for_status()
        logger.debug(f"Chart {symbol}/{cycle_key} ok req_id={_req_id(resp)}")
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch {symbol}/{cycle_key}: {e}")
        return None


def get_settings() -> dict | None:
    logger.debug("Fetching stonks settings")
    try:
        resp = requests.get(f"{_BASE}/stonks/settings", timeout=5)
        resp.raise_for_status()
        logger.debug(f"Stonks settings ok req_id={_req_id(resp)}")
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch stonks settings: {e}")
        return None


def set_current(symbol: str, cycle_key: str) -> None:
    logger.debug(f"Setting current display state: {symbol}/{cycle_key}")
    try:
        resp = requests.put(
            f"{_BASE}/stonks/now",
            json={"symbol": symbol, "cycle_key": cycle_key},
            timeout=2,
        )
        logger.debug(f"set_current ok req_id={_req_id(resp)}")
    except requests.RequestException as e:
        logger.warning(f"Failed to report current display state: {e}")


def get_log_level() -> str:
    try:
        resp = requests.get(f"{_BASE}/system/log-level", timeout=3)
        resp.raise_for_status()
        return resp.json().get("log_level", "INFO")
    except requests.RequestException:
        return "INFO"
