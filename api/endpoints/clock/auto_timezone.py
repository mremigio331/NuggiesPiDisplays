"""Auto-detect the clock timezone from the device's public IP.

When the clock is in auto mode (``clock.timezone_auto`` is true), the device
resolves its IANA timezone from its public IP on startup. This keeps the clock
correct out of the box and if the device physically moves, while never
overriding a timezone the user has set manually (which flips ``timezone_auto``
off — see clock/update_settings.py).
"""

import logging
from zoneinfo import ZoneInfo
from helpers.config import read_settings, write_settings
from helpers.geolocation import get_ip_geolocation
from .ws_manager import manager

logger = logging.getLogger(__name__)


async def auto_detect_timezone() -> None:
    """Detect and persist the timezone from IP when in auto mode.

    No-op if ``timezone_auto`` is off, geolocation fails, or the detected
    timezone is invalid / unchanged. Broadcasts to connected clock displays
    on change so a running clock updates live.
    """
    settings = read_settings()
    clock = settings.get("clock", {})

    if not clock.get("timezone_auto", False):
        logger.debug("Clock timezone_auto is off — skipping IP timezone detection")
        return

    loc = get_ip_geolocation()
    tz = (loc or {}).get("timezone", "")
    if not tz:
        logger.info("Could not auto-detect timezone from IP — keeping current value")
        return

    # Guard against a bad value from the upstream service.
    try:
        ZoneInfo(tz)
    except Exception:
        logger.warning(f"IP geolocation returned an invalid timezone: {tz!r}")
        return

    if tz == clock.get("timezone"):
        logger.debug(f"Auto-detected timezone unchanged ({tz})")
        return

    clock["timezone"] = tz
    settings["clock"] = clock
    write_settings(settings)
    logger.info(f"Auto-detected clock timezone from IP: {tz}")

    try:
        await manager.broadcast(clock)
    except Exception as e:
        logger.debug(f"Clock broadcast after timezone auto-detect failed: {e}")
