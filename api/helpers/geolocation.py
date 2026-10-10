"""Shared IP-based geolocation helper.

Uses the free ip-api.com service to resolve the device's approximate
location and timezone from its public IP address. This single helper is
reused by:
  - the weather feature (needs latitude / longitude / city label), and
  - the clock feature (needs an IANA timezone suggestion).

ip-api.com returns an IANA timezone name (e.g. "America/New_York") in the
``timezone`` field, which maps directly onto the clock's stored format.
"""

import logging
import requests

logger = logging.getLogger(__name__)

_IP_API_URL = "http://ip-api.com/json/"
_TIMEOUT = 5


def get_ip_geolocation() -> dict | None:
    """Resolve approximate location + timezone from the public IP.

    Returns a dict with keys ``latitude``, ``longitude``, ``city_label`` and
    ``timezone`` on success, or ``None`` if the lookup fails for any reason.
    """
    try:
        resp = requests.get(_IP_API_URL, timeout=_TIMEOUT)
        resp.raise_for_status()
        d = resp.json()
        if d.get("status") != "success":
            logger.warning(
                f"IP geolocation returned non-success status: {d.get('message')}"
            )
            return None

        city = d.get("city", "")
        region = d.get("regionName", "")
        city_label = ", ".join(p for p in [city, region] if p)

        return {
            "latitude": d.get("lat"),
            "longitude": d.get("lon"),
            "city_label": city_label,
            "timezone": d.get("timezone", ""),
        }
    except Exception as e:
        logger.warning(f"IP geolocation failed: {e}")
        return None
