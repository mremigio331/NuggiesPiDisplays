import logging
import requests

_BASE = "http://localhost:8000"
logger = logging.getLogger(__name__)


def get_weather() -> dict | None:
    try:
        resp = requests.get(f"{_BASE}/weather/data", timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch weather data: %s", e)
        return None


def get_settings() -> dict | None:
    try:
        resp = requests.get(f"{_BASE}/weather/settings", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch weather settings: %s", e)
        return None
