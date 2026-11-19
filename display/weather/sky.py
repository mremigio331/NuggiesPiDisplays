"""
Sun / moon position for the weather "sky" screen. Pure logic, no drawing.

Day   (sunrise -> sunset):          the sun travels left to right.
Night (sunset -> next sunrise):     the moon travels left to right.
The moon phase is computed from the date (Open-Meteo does not supply it).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

SYNODIC_MONTH = 29.530588853  # days between new moons
_KNOWN_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)


def moon_phase(now_utc: datetime) -> float:
    """0.0 = new moon, 0.25 = first quarter, 0.5 = full, 0.75 = last quarter."""
    days = (now_utc - _KNOWN_NEW_MOON).total_seconds() / 86400.0
    return (days % SYNODIC_MONTH) / SYNODIC_MONTH


def _parse(value) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def compute(sky: dict | None, now_utc: datetime | None = None) -> dict | None:
    """Return {body, progress, phase, local_now} or None when sun times are
    unavailable (e.g. polar day/night), so the caller can skip the screen."""
    if not sky:
        return None
    now_utc = now_utc or datetime.now(timezone.utc)

    sunrises = [_parse(v) for v in sky.get("sunrise", [])]
    sunsets = [_parse(v) for v in sky.get("sunset", [])]
    if not sunrises or not sunsets or sunrises[0] is None or sunsets[0] is None:
        return None
    sunrise, sunset = sunrises[0], sunsets[0]
    next_sunrise = (
        sunrises[1]
        if len(sunrises) > 1 and sunrises[1]
        else sunrise + timedelta(days=1)
    )

    # Current time at the weather location, as a naive datetime like the API times.
    offset = timedelta(seconds=int(sky.get("utc_offset_seconds") or 0))
    local_now = (now_utc + offset).replace(tzinfo=None)

    if local_now < sunrise:
        # Before dawn: the night began at yesterday's sunset (about 24h earlier).
        body = "moon"
        start, end = sunset - timedelta(days=1), sunrise
    elif local_now <= sunset:
        body = "sun"
        start, end = sunrise, sunset
    else:
        body = "moon"
        start, end = sunset, next_sunrise

    span = (end - start).total_seconds()
    progress = (local_now - start).total_seconds() / span if span > 0 else 0.0
    return {
        "body": body,
        "progress": min(1.0, max(0.0, progress)),
        "phase": moon_phase(now_utc),
        "local_now": local_now,
    }
