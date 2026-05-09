import logging
import requests

_BASE = "http://localhost:8000"
logger = logging.getLogger(__name__)


def get_next_four() -> dict | None:
    try:
        resp = requests.get(f"{_BASE}/mta/trains/next_four", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch next four trains: %s", e)
        return None


def get_mta_settings() -> dict | None:
    try:
        resp = requests.get(f"{_BASE}/mta/configs", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch MTA settings: %s", e)
        return None


def get_enabled_stations() -> list | None:
    try:
        resp = requests.get(f"{_BASE}/mta/stations/enabled", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error("Failed to fetch enabled stations: %s", e)
        return None


def set_station(station: str) -> bool:
    try:
        resp = requests.put(
            f"{_BASE}/mta/stations/current", json={"station": station}, timeout=10
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error("Failed to set station to %s: %s", station, e)
        return False
