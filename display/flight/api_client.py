import io
import logging
import requests

from config import API_BASE as _BASE

logger = logging.getLogger(__name__)


def get_nearby() -> dict | None:
    """Planes near the saved spot. A 503 still carries a body (an error and
    whether a spot is set), so it is returned too. None means no API."""
    try:
        # The API may be mid-fetch from three upstream feeds (8 s each).
        resp = requests.get(f"{_BASE}/flight/nearby", timeout=30)
        if resp.status_code in (200, 503):
            return resp.json()
        logger.error(f"Flight nearby returned {resp.status_code}")
    except (requests.RequestException, ValueError) as e:
        logger.error(f"Failed to fetch nearby flights: {e}")
    return None


def get_logo(code: str):
    """16x16 RGB logo for an airline IATA code, or None."""
    try:
        resp = requests.get(
            f"{_BASE}/flight/logo/{code}.png", params={"size": 16}, timeout=25
        )
        if resp.status_code != 200:
            return None
        from PIL import Image

        return Image.open(io.BytesIO(resp.content)).convert("RGB").resize((16, 16))
    except Exception as e:
        logger.warning(f"Logo fetch failed for {code}: {e}")
        return None


def get_log_level() -> str:
    try:
        resp = requests.get(f"{_BASE}/system/log-level", timeout=3)
        resp.raise_for_status()
        return resp.json().get("log_level", "INFO")
    except requests.RequestException:
        return "INFO"
