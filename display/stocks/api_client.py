import logging
import requests

_BASE = "http://localhost:8000"
logger = logging.getLogger(__name__)


def get_stock_chart(symbol: str, cycle_key: str) -> dict | None:
    try:
        resp = requests.get(f"{_BASE}/stonks/{symbol}/{cycle_key}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch %s/%s: %s", symbol, cycle_key, e)
        return None


def get_settings() -> dict | None:
    try:
        resp = requests.get(f"{_BASE}/stonks/settings", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch stonks settings: %s", e)
        return None


def set_current(symbol: str, cycle_key: str) -> None:
    try:
        requests.put(
            f"{_BASE}/stonks/now",
            json={"symbol": symbol, "cycle_key": cycle_key},
            timeout=2,
        )
    except requests.RequestException as e:
        logger.warning("Failed to report current display state: %s", e)
