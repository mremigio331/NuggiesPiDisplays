import logging
import requests

_BASE = "http://localhost:8000"
logger = logging.getLogger(__name__)


def get_settings() -> dict | None:
    try:
        resp = requests.get(f"{_BASE}/clock/settings", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch clock settings: %s", e)
        return None
