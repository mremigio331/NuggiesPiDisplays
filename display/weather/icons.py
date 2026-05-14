"""
Pixel-art weather icons for the 64×32 RGB matrix.

Each icon is a list of (dx, dy, r, g, b) tuples relative to the top-left corner.
All icons fit inside an 8×8 bounding box and are designed for the dark matrix background.

draw_icon(canvas, icon_key, x, y, scale=1) renders any icon at the given position.
scale=2 doubles every pixel → 16×16, useful for the current-conditions screen.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
_SY = (255, 200, 0)  # sun yellow
_SO = (255, 140, 0)  # sun ray orange
_CW = (210, 225, 240)  # cloud white/pale-blue (fair weather)
_CD = (160, 175, 195)  # cloud dark grey (rain/storm clouds)
_RB = (80, 140, 255)  # rain blue
_SN = (200, 230, 255)  # snow white-blue
_LT = (255, 240, 0)  # lightning yellow
_SC = (100, 105, 130)  # storm cloud dark purple-grey
_FG = (155, 160, 175)  # fog grey

# ---------------------------------------------------------------------------
# Icon pixel maps
# ---------------------------------------------------------------------------

# ── Sunny ──────────────────────────────────────────────────────────────────
SUNNY = [
    # sun body
    (3, 2, *_SY),
    (4, 2, *_SY),
    (2, 3, *_SY),
    (3, 3, *_SY),
    (4, 3, *_SY),
    (5, 3, *_SY),
    (2, 4, *_SY),
    (3, 4, *_SY),
    (4, 4, *_SY),
    (5, 4, *_SY),
    (3, 5, *_SY),
    (4, 5, *_SY),
    # rays — cardinal
    (3, 0, *_SO),
    (4, 0, *_SO),
    (3, 7, *_SO),
    (4, 7, *_SO),
    (0, 3, *_SO),
    (0, 4, *_SO),
    (7, 3, *_SO),
    (7, 4, *_SO),
    # rays — diagonal
    (1, 1, *_SO),
    (6, 1, *_SO),
    (1, 6, *_SO),
    (6, 6, *_SO),
]

# ── Partly Cloudy ──────────────────────────────────────────────────────────
PARTLY_CLOUDY = [
    # small sun, top-right
    (5, 0, *_SO),
    (4, 1, *_SY),
    (5, 1, *_SY),
    (6, 1, *_SY),
    (5, 2, *_SO),
    (7, 1, *_SO),
    # cloud, lower-left (overlaps sun slightly)
    (1, 2, *_CW),
    (2, 2, *_CW),
    (3, 2, *_CW),
    (0, 3, *_CW),
    (1, 3, *_CW),
    (2, 3, *_CW),
    (3, 3, *_CW),
    (4, 3, *_CW),
    (5, 3, *_CW),
    (6, 3, *_CW),
    (0, 4, *_CW),
    (1, 4, *_CW),
    (2, 4, *_CW),
    (3, 4, *_CW),
    (4, 4, *_CW),
    (5, 4, *_CW),
    (6, 4, *_CW),
    (7, 4, *_CW),
    (0, 5, *_CW),
    (1, 5, *_CW),
    (2, 5, *_CW),
    (3, 5, *_CW),
    (4, 5, *_CW),
    (5, 5, *_CW),
    (6, 5, *_CW),
    (7, 5, *_CW),
]

# ── Cloudy ─────────────────────────────────────────────────────────────────
CLOUDY = [
    # top bump
    (2, 1, *_CW),
    (3, 1, *_CW),
    (4, 1, *_CW),
    # main body
    (1, 2, *_CW),
    (2, 2, *_CW),
    (3, 2, *_CW),
    (4, 2, *_CW),
    (5, 2, *_CW),
    (6, 2, *_CW),
    (0, 3, *_CW),
    (1, 3, *_CW),
    (2, 3, *_CW),
    (3, 3, *_CW),
    (4, 3, *_CW),
    (5, 3, *_CW),
    (6, 3, *_CW),
    (7, 3, *_CW),
    (0, 4, *_CW),
    (1, 4, *_CW),
    (2, 4, *_CW),
    (3, 4, *_CW),
    (4, 4, *_CW),
    (5, 4, *_CW),
    (6, 4, *_CW),
    (7, 4, *_CW),
]

# ── Foggy ──────────────────────────────────────────────────────────────────
FOGGY = [
    *[(x, 0, *_FG) for x in range(8)],
    *[(x, 2, *_FG) for x in range(1, 7)],
    *[(x, 4, *_FG) for x in range(8)],
    *[(x, 6, *_FG) for x in range(1, 7)],
]

# ── Drizzle ────────────────────────────────────────────────────────────────
DRIZZLE = [
    # light cloud
    (2, 0, *_CW),
    (3, 0, *_CW),
    (4, 0, *_CW),
    (1, 1, *_CW),
    (2, 1, *_CW),
    (3, 1, *_CW),
    (4, 1, *_CW),
    (5, 1, *_CW),
    (6, 1, *_CW),
    (0, 2, *_CW),
    (1, 2, *_CW),
    (2, 2, *_CW),
    (3, 2, *_CW),
    (4, 2, *_CW),
    (5, 2, *_CW),
    (6, 2, *_CW),
    (7, 2, *_CW),
    (0, 3, *_CW),
    (1, 3, *_CW),
    (2, 3, *_CW),
    (3, 3, *_CW),
    (4, 3, *_CW),
    (5, 3, *_CW),
    (6, 3, *_CW),
    (7, 3, *_CW),
    # sparse light drops
    (1, 5, *_RB),
    (4, 5, *_RB),
    (7, 5, *_RB),
    (2, 7, *_RB),
    (5, 7, *_RB),
]

# ── Rainy ──────────────────────────────────────────────────────────────────
RAINY = [
    # darker rain cloud
    (2, 0, *_CD),
    (3, 0, *_CD),
    (4, 0, *_CD),
    (1, 1, *_CD),
    (2, 1, *_CD),
    (3, 1, *_CD),
    (4, 1, *_CD),
    (5, 1, *_CD),
    (6, 1, *_CD),
    (0, 2, *_CD),
    (1, 2, *_CD),
    (2, 2, *_CD),
    (3, 2, *_CD),
    (4, 2, *_CD),
    (5, 2, *_CD),
    (6, 2, *_CD),
    (7, 2, *_CD),
    (0, 3, *_CD),
    (1, 3, *_CD),
    (2, 3, *_CD),
    (3, 3, *_CD),
    (4, 3, *_CD),
    (5, 3, *_CD),
    (6, 3, *_CD),
    (7, 3, *_CD),
    # rain drops (diagonal streaks)
    (1, 4, *_RB),
    (3, 4, *_RB),
    (5, 4, *_RB),
    (7, 4, *_RB),
    (0, 5, *_RB),
    (2, 5, *_RB),
    (4, 5, *_RB),
    (6, 5, *_RB),
    (1, 6, *_RB),
    (3, 6, *_RB),
    (5, 6, *_RB),
]

# ── Snowy ──────────────────────────────────────────────────────────────────
SNOWY = [
    # cloud (same shape as rainy)
    (2, 0, *_CD),
    (3, 0, *_CD),
    (4, 0, *_CD),
    (1, 1, *_CD),
    (2, 1, *_CD),
    (3, 1, *_CD),
    (4, 1, *_CD),
    (5, 1, *_CD),
    (6, 1, *_CD),
    (0, 2, *_CD),
    (1, 2, *_CD),
    (2, 2, *_CD),
    (3, 2, *_CD),
    (4, 2, *_CD),
    (5, 2, *_CD),
    (6, 2, *_CD),
    (7, 2, *_CD),
    (0, 3, *_CD),
    (1, 3, *_CD),
    (2, 3, *_CD),
    (3, 3, *_CD),
    (4, 3, *_CD),
    (5, 3, *_CD),
    (6, 3, *_CD),
    (7, 3, *_CD),
    # snowflake dots
    (0, 5, *_SN),
    (2, 5, *_SN),
    (4, 5, *_SN),
    (6, 5, *_SN),
    (1, 6, *_SN),
    (3, 6, *_SN),
    (5, 6, *_SN),
    (7, 6, *_SN),
    (0, 7, *_SN),
    (2, 7, *_SN),
    (4, 7, *_SN),
    (6, 7, *_SN),
]

# ── Thunderstorm ───────────────────────────────────────────────────────────
THUNDERSTORM = [
    # dark storm cloud
    (2, 0, *_SC),
    (3, 0, *_SC),
    (4, 0, *_SC),
    (1, 1, *_SC),
    (2, 1, *_SC),
    (3, 1, *_SC),
    (4, 1, *_SC),
    (5, 1, *_SC),
    (6, 1, *_SC),
    (0, 2, *_SC),
    (1, 2, *_SC),
    (2, 2, *_SC),
    (3, 2, *_SC),
    (4, 2, *_SC),
    (5, 2, *_SC),
    (6, 2, *_SC),
    (7, 2, *_SC),
    (0, 3, *_SC),
    (1, 3, *_SC),
    (2, 3, *_SC),
    (3, 3, *_SC),
    (4, 3, *_SC),
    (5, 3, *_SC),
    (6, 3, *_SC),
    (7, 3, *_SC),
    # lightning bolt  ⚡
    (4, 4, *_LT),
    (5, 4, *_LT),
    (3, 5, *_LT),
    (4, 5, *_LT),
    (2, 6, *_LT),
    (3, 6, *_LT),
    (4, 6, *_LT),
    (3, 7, *_LT),
]

# ---------------------------------------------------------------------------
# Registry + helpers
# ---------------------------------------------------------------------------

ICONS: dict[str, list] = {
    "sunny": SUNNY,
    "partly_cloudy": PARTLY_CLOUDY,
    "cloudy": CLOUDY,
    "foggy": FOGGY,
    "drizzle": DRIZZLE,
    "rainy": RAINY,
    "snowy": SNOWY,
    "thunderstorm": THUNDERSTORM,
}


def wmo_to_icon(code: int) -> str:
    if code == 0:
        return "sunny"
    if code in (1, 2):
        return "partly_cloudy"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "foggy"
    if code in (51, 53, 55, 56, 57):
        return "drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "rainy"
    if code in (71, 73, 75, 77, 85, 86):
        return "snowy"
    if code in (95, 96, 99):
        return "thunderstorm"
    return "cloudy"


def draw_icon(canvas, icon_key: str, x: int, y: int, scale: int = 1) -> None:
    """Draw a weather icon at (x, y). scale=2 → 16×16 double-size version."""
    pixels = ICONS.get(icon_key, CLOUDY)
    for dx, dy, r, g, b in pixels:
        for sy in range(scale):
            for sx in range(scale):
                canvas.SetPixel(x + dx * scale + sx, y + dy * scale + sy, r, g, b)
