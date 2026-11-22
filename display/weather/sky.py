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


# ---------------------------------------------------------------------------
# Weather on the sky screen. Pure pixel maths (no drawing) so the website's
# SkyCard.js can mirror it exactly — keep the two in sync.
# ---------------------------------------------------------------------------


def condition(code) -> str:
    """Open-Meteo WMO weather code -> sky condition."""
    try:
        code = int(code)
    except (TypeError, ValueError):
        return "clear"
    if code == 0:
        return "clear"
    if code == 1:
        return "mostly_clear"
    if code == 2:
        return "partly"
    if code == 3:
        return "overcast"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57):
        return "drizzle"
    if code in (65, 67, 82):
        return "heavy_rain"
    if code in (61, 63, 66, 80, 81):
        return "rain"
    if code in (75, 86):
        return "heavy_snow"
    if code in (71, 73, 77, 85):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "overcast"  # unknown code: the safe "no sun" look


# How the sun/moon shows for each condition: "show", "dim" or "hide".
# How the sun/moon shows: always drawn, so its position still reads on cloudy
# days (the clouds are drawn over it). Fog dims it.
_BODY = {"fog": "dim"}

# Constellations for clear nights: the Big Dipper (left) and Orion (right).
_DIPPER = [(1, 8), (4, 9), (7, 10), (10, 11), (10, 14), (15, 14), (15, 10)]
_ORION = [(51, 14), (53, 13), (55, 12), (57, 9), (49, 19)]  # belt, Bellatrix, Saiph
_BETELGEUSE = (48, 8)  # Orion's red shoulder
_RIGEL = (58, 18)  # Orion's blue foot
_FAINT_STARS = [(3, 11), (11, 9), (20, 12), (42, 9), (52, 14), (60, 9)]

# A cartoon cloud, 14 x 6: "o" outline, "w" fill, "s" shaded underside.
_CLOUD = [
    ".....oooo.....",
    "..ooowwwwo....",
    ".owwwwwwwwooo.",
    "owwwwwwwwwwwwo",
    "osssssssssssso",
    ".oooooooooooo.",
]
_CLOUDS_AT = {  # scattered clouds (top-left corners), set above the sun's path
    "mostly_clear": [(44, 9)],
    "partly": [(2, 10), (44, 9)],
}
# A full sky of overlapping clouds for overcast, rain, snow and storms. Each
# one is drawn over the last, so the outlines keep every puff readable.
_DECK_AT = [(-3, 9), (9, 8), (21, 9), (33, 8), (45, 9), (57, 8)]


def _cloud_pixels(ox: int, oy: int, line, fill, shade) -> list:
    out = []
    for row, text in enumerate(_CLOUD):
        for col, ch in enumerate(text):
            if ch != ".":
                rgb = line if ch == "o" else shade if ch == "s" else fill
                out.append((ox + col, oy + row, rgb))
    return out


# (column step, drop length, colour key) for falling weather
_FALL = {
    "drizzle": (6, 1, "rain"),
    "rain": (4, 2, "rain"),
    "heavy_rain": (3, 2, "rain"),
    "storm": (3, 2, "rain"),
    "snow": (5, 1, "snow"),
    "heavy_snow": (3, 1, "snow"),
}
_BOLT = [  # zig-zag lightning bolt under the clouds
    (16, 14),
    (15, 15),
    (14, 16),
    (13, 17),
    (14, 17),
    (15, 17),
    (14, 18),
    (13, 19),
    (12, 20),
]
_FOG_ROWS = (16, 19, 22)

_DAY = {
    "cloud_line": (70, 80, 105),
    "cloud": (240, 245, 255),
    "cloud_shade": (165, 175, 195),
    "deck_line": (70, 75, 95),
    "deck": (185, 190, 205),
    "deck_shade": (125, 130, 150),
    "storm_line": (35, 35, 50),
    "storm": (105, 105, 125),
    "storm_shade": (70, 70, 88),
    "rain": (80, 140, 255),
    "snow": (220, 230, 255),
    "fog": (120, 125, 140),
}
_NIGHT = {
    "cloud_line": (35, 38, 52),
    "cloud": (120, 125, 145),
    "cloud_shade": (80, 85, 105),
    "deck_line": (30, 32, 44),
    "deck": (85, 88, 105),
    "deck_shade": (58, 60, 75),
    "storm_line": (20, 20, 30),
    "storm": (55, 55, 70),
    "storm_shade": (40, 40, 52),
    "rain": (50, 90, 170),
    "snow": (150, 160, 185),
    "fog": (60, 62, 72),
}
_STAR = (150, 155, 180)
_STAR_FAINT = (90, 95, 120)
_STAR_RED = (220, 120, 90)
_STAR_BLUE = (160, 185, 255)
_LIGHTNING = (255, 240, 0)


def scene(code, night: bool, minute: int, ground_top) -> dict:
    """Weather layers for the sky screen.

    ground_top(x) gives the first mountain row in column x; falling rain and
    snow stop there so it looks like it falls behind the mountain.

    Returns {"body": "show"|"dim"|"hide",
             "back":  [(x, y, rgb)]  drawn before the sun/moon,
             "front": [(x, y, rgb)]  drawn after the sun/moon,
             "over":  [(x, y, rgb)]  drawn after the mountain}
    """
    cond = condition(code)
    pal = _NIGHT if night else _DAY
    back, front, over = [], [], []

    # Stars: constellations on clear nights, a few faint ones when partly cloudy
    if night and cond in ("clear", "mostly_clear"):
        for x, y in _FAINT_STARS:
            back.append((x, y, _STAR_FAINT))
        for x, y in _DIPPER + _ORION:
            back.append((x, y, _STAR))
        back.append((*_BETELGEUSE, _STAR_RED))
        back.append((*_RIGEL, _STAR_BLUE))
    elif night and cond == "partly":
        for x, y in _FAINT_STARS:
            back.append((x, y, _STAR_FAINT))

    # Falling rain / snow. The pattern shifts each minute, so it drifts down.
    if cond in _FALL:
        step, length, key = _FALL[cond]
        for x in range(1, 64, step):
            for base in range(15, 32, 6):
                y0 = base + (x * 3 + minute) % 6
                for y in range(y0, y0 + length):
                    if y < ground_top(x):
                        back.append((x, y, pal[key]))
    if cond == "storm":  # in front of the sun/moon, under the clouds
        for x, y in _BOLT:
            front.append((x, y, _LIGHTNING))

    # Scattered clouds pass in front of the sun/moon
    for ox, oy in _CLOUDS_AT.get(cond, []):
        front += _cloud_pixels(
            ox, oy, pal["cloud_line"], pal["cloud"], pal["cloud_shade"]
        )

    # A sky full of clouds hides the sun/moon for overcast, rain, snow, storms
    if cond in ("overcast", "drizzle", "rain", "heavy_rain", "snow", "heavy_snow"):
        kind = "deck"
    elif cond == "storm":
        kind = "storm"
    else:
        kind = None
    if kind:
        for ox, oy in _DECK_AT:
            front += _cloud_pixels(
                ox, oy, pal[kind + "_line"], pal[kind], pal[kind + "_shade"]
            )

    # Fog: dashed bands drifting across the mountain
    if cond == "fog":
        for y in _FOG_ROWS:
            for x in range(64):
                if (x + y * 3 + minute) % 9 < 6:
                    over.append((x, y, pal["fog"]))

    return {"body": _BODY.get(cond, "show"), "back": back, "front": front, "over": over}
