import logging
import requests

from config import API_BASE as _BASE

logger = logging.getLogger(__name__)


def _req_id(resp: requests.Response) -> str:
    return resp.headers.get("X-Request-ID", "-")


def get_next_four() -> dict | None:
    logger.debug("Fetching next four trains")
    try:
        resp = requests.get(f"{_BASE}/mta/trains/next_four", timeout=10)
        resp.raise_for_status()
        logger.debug(f"Next four trains ok req_id={_req_id(resp)}")
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch next four trains: {e}")
        return None


def get_mta_settings() -> dict | None:
    logger.debug("Fetching MTA settings")
    try:
        resp = requests.get(f"{_BASE}/mta/configs", timeout=10)
        resp.raise_for_status()
        logger.debug(f"MTA settings ok req_id={_req_id(resp)}")
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch MTA settings: {e}")
        return None


def get_enabled_stations() -> list | None:
    logger.debug("Fetching enabled stations")
    try:
        resp = requests.get(f"{_BASE}/mta/stations/enabled", timeout=10)
        resp.raise_for_status()
        logger.debug(f"Enabled stations ok req_id={_req_id(resp)}")
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch enabled stations: {e}")
        return None


def set_station(station: str) -> bool:
    logger.debug(f"Setting station to {station!r}")
    try:
        resp = requests.put(
            f"{_BASE}/mta/stations/current", json={"station": station}, timeout=10
        )
        resp.raise_for_status()
        logger.debug(f"set_station ok req_id={_req_id(resp)}")
        return True
    except requests.RequestException as e:
        logger.error(f"Failed to set station to {station!r}: {e}")
        return False


def get_log_level() -> str:
    try:
        resp = requests.get(f"{_BASE}/system/log-level", timeout=3)
        resp.raise_for_status()
        return resp.json().get("log_level", "INFO")
    except requests.RequestException:
        return "INFO"
