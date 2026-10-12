import logging
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.config import read_settings

logger = logging.getLogger(__name__)
router = APIRouter()


def local_timezone() -> str:
    """Best-effort IANA name for the device's local timezone.

    Reads /etc/timezone (Debian/Raspberry Pi OS), then falls back to the
    /etc/localtime symlink target, then UTC.
    """
    try:
        tz = Path("/etc/timezone").read_text().strip()
        if tz:
            return tz
    except OSError:
        pass
    try:
        link = Path("/etc/localtime").resolve()
        parts = link.parts
        if "zoneinfo" in parts:
            idx = parts.index("zoneinfo")
            tz = "/".join(parts[idx + 1 :])
            if tz:
                return tz
    except OSError:
        pass
    return "UTC"


def normalize_clock(clock: dict) -> dict:
    """Return the clock settings in the current schema.

    Migrates older on-disk settings (single `timezone` / `timezone_auto` /
    `mode` / `world_timezones`) into the new model: an ordered `timezones`
    list, `display_mode` ("focus"|"multi"), and `cycle_seconds`. The device's
    local timezone is always kept in the list so the current time is shown by
    default.
    """
    clock = dict(clock or {})
    local_tz = local_timezone()

    if "timezones" not in clock:
        zones = []
        # Old single timezone becomes the first entry.
        if clock.get("timezone"):
            zones.append(clock["timezone"])
        # Old world list appends after it.
        for z in clock.get("world_timezones", []) or []:
            if z not in zones:
                zones.append(z)
        # New install / no prior timezone: default to the device's local zone
        # so the current time is shown out of the box.
        if not zones:
            zones = [local_tz]
        clock["timezones"] = zones

    # Never serve an empty list; fall back to the local zone.
    if not clock["timezones"]:
        clock["timezones"] = [local_tz]

    if "display_mode" not in clock:
        # Old "world" mode maps to the new "multi"; everything else to "focus".
        clock["display_mode"] = "multi" if clock.get("mode") == "world" else "focus"

    clock.setdefault("cycle_seconds", 5)
    clock.setdefault("color", [255, 255, 255])
    clock.setdefault("use_24h", False)

    # Drop obsolete keys so clients only see the current schema.
    for stale in ("timezone", "timezone_auto", "mode", "world_timezones"):
        clock.pop(stale, None)

    return clock


@router.get("/settings")
async def get_settings():
    settings = read_settings()
    return JSONResponse(normalize_clock(settings.get("clock", {})))
