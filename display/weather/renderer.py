"""
Weather display renderer — three cycling screens on the 64×32 RGB matrix.

Screen 1 (current):   large icon + temperature + feels-like + condition + city
Screen 2 (hourly):    6 columns — time label / icon / temp
Screen 3 (forecast):  5 columns — day / icon / hi / lo
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import sky as sky_mod
from icons import draw_icon, wmo_to_icon
from matrix import USING_HARDWARE

MATRIX_W = 64
MATRIX_H = 32

_FONT_DIR = Path(__file__).parent.parent / "fonts"
_BDF_LARGE = _FONT_DIR / "5x8.bdf"  # 5×8: primary text
_BDF_SMALL = _FONT_DIR / "4x6.bdf"  # 4×6: secondary / compact text

_CW_LARGE = 5  # char width for 5×8 font
_CW_SMALL = 4  # char width for 4×6 font

# Hardware font handles (populated below)
_gfx = None
_hw_large = None
_hw_small = None

if USING_HARDWARE:
    try:
        from rgbmatrix import graphics as _gfx

        if _BDF_LARGE.exists():
            _hw_large = _gfx.Font()
            _hw_large.LoadFont(str(_BDF_LARGE))
        if _BDF_SMALL.exists():
            _hw_small = _gfx.Font()
            _hw_small.LoadFont(str(_BDF_SMALL))
    except Exception:
        _gfx = None

# PIL fallback fonts for headless / mock mode
try:
    from PIL import ImageFont

    _pil_large = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 8
    )
    _pil_small = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 6
    )
except Exception:
    try:
        from PIL import ImageFont

        _pil_large = ImageFont.load_default()
        _pil_small = _pil_large
    except Exception:
        _pil_large = _pil_small = None


# ---------------------------------------------------------------------------
# Low-level drawing helpers
# ---------------------------------------------------------------------------


def _color(r, g, b):
    if _gfx:
        return _gfx.Color(r, g, b)
    return (r, g, b)


def _draw_text(
    canvas, text: str, x: int, baseline_y: int, color, font: str = "large"
) -> None:
    """Draw text on the canvas using hardware BDF fonts or PIL fallback."""
    if _gfx and _hw_large and _hw_small:
        hw_font = _hw_large if font == "large" else _hw_small
        _gfx.DrawText(canvas, hw_font, x, baseline_y, color, text)
    else:
        # PIL mock path
        try:
            from PIL import ImageDraw

            draw = ImageDraw.Draw(canvas._image)
            pil_font = _pil_large if font == "large" else _pil_small
            draw.text((x, baseline_y - 8), text, font=pil_font, fill=color)
        except Exception:
            pass


def _clear(canvas) -> None:
    canvas.Clear()


# ---------------------------------------------------------------------------
# Screen 1 — Current conditions
# ---------------------------------------------------------------------------
#
# Layout (64×32):
#   x= 0-15  icon 16×16 (scale=2), vertically centred  y=8..23
#   x=18-63  temp    (5×8,  baseline y= 9)
#            desc    (4×6,  baseline y=18)
#            H:XX L:XX (4×6, baseline y=27)
#
def render_current(canvas, data: dict) -> None:
    _clear(canvas)
    current = data.get("current", {})
    daily = data.get("daily", [])

    temp = current.get("temperature", 0)
    wcode = current.get("weather_code", 0)
    desc = current.get("weather_desc", "")
    unit_s = current.get("unit_symbol", "°F")

    today = daily[0] if daily else {}
    hi = today.get("temp_max", "")
    lo = today.get("temp_min", "")

    icon_key = wmo_to_icon(wcode)
    draw_icon(canvas, icon_key, x=0, y=8, scale=2)  # 16×16 centred in 32-tall matrix

    white = _color(255, 255, 255)
    gray = _color(160, 170, 190)
    yellow = _color(255, 210, 80)

    _draw_text(canvas, f"{temp}{unit_s}", x=18, baseline_y=9, color=white, font="large")
    _draw_text(canvas, desc[:14], x=18, baseline_y=18, color=yellow, font="small")
    if hi != "" or lo != "":
        _draw_text(
            canvas, f"H:{hi} L:{lo}", x=18, baseline_y=27, color=gray, font="small"
        )


# ---------------------------------------------------------------------------
# Screen 2 — Hourly (3 columns, current time header)
# ---------------------------------------------------------------------------
#
# Layout (64×32), 3 columns at x=2, 23, 44 (each ~20px wide):
#   y=0-7:   current time "3:45P" (4×6, baseline y=7)
#   y=9-15:  column labels "+1h" "+2h" "+3h" (4×6, baseline y=15)
#   y=17-24: 8×8 icon centered in column
#   y=25-31: temperature (4×6, baseline y=31)
#
_COL_X = [2, 23, 44]


def render_hourly(canvas, data: dict) -> None:
    _clear(canvas)
    hourly = data.get("hourly", [])

    white = _color(255, 255, 255)
    gray = _color(140, 160, 185)
    cyan = _color(100, 190, 220)

    # Current time header
    now = datetime.now()
    h = now.hour % 12 or 12
    ap = "A" if now.hour < 12 else "P"
    now_str = f"{h}:{now.strftime('%M')}{ap}"
    _draw_text(canvas, now_str, x=0, baseline_y=7, color=white, font="small")

    # Slots 1-3 are the next 3 hours (+1h, +2h, +3h)
    for i, x in enumerate(_COL_X):
        slot_idx = i + 1
        if slot_idx >= len(hourly):
            break
        slot = hourly[slot_idx]
        temp = slot.get("temperature", 0)
        wcode = slot.get("weather_code", 0)
        icon_key = wmo_to_icon(wcode)

        _draw_text(canvas, f"+{i+1}h", x=x, baseline_y=15, color=gray, font="small")
        draw_icon(canvas, icon_key, x=x + 6, y=17, scale=1)
        _draw_text(canvas, str(temp), x=x + 2, baseline_y=31, color=cyan, font="small")


# ---------------------------------------------------------------------------
# Screen 3 — 3-day forecast (3 columns, same x positions as hourly)
# ---------------------------------------------------------------------------
#
# Layout (64×32), 3 columns at x=2, 23, 44 (each ~20px wide):
#   y=0-7:   3-letter day label "Mon","Tue","Wed" (4×6, baseline y=7)
#   y=9-16:  8×8 icon centered in column
#   y=18-24: high temp (4×6, baseline y=24) — white
#   y=25-31: low temp  (4×6, baseline y=31) — gold
#
def render_forecast(canvas, data: dict) -> None:
    _clear(canvas)
    daily = data.get("daily", [])

    white = _color(255, 255, 255)
    gold = _color(230, 180, 50)
    cyan = _color(100, 190, 220)

    for i, x in enumerate(_COL_X):
        if i >= len(daily):
            break
        day = daily[i]
        day_lbl = day.get("day_label", "")
        hi = day.get("temp_max", 0)
        lo = day.get("temp_min", 0)
        wcode = day.get("weather_code", 0)
        icon_key = wmo_to_icon(wcode)

        _draw_text(canvas, day_lbl, x=x, baseline_y=7, color=cyan, font="small")
        draw_icon(canvas, icon_key, x=x + 6, y=9, scale=1)
        _draw_text(canvas, str(hi), x=x + 2, baseline_y=24, color=white, font="small")
        _draw_text(canvas, str(lo), x=x + 2, baseline_y=31, color=gold, font="small")


# ---------------------------------------------------------------------------
# Screen 4 — Sky (sun by day, moon by night, over Mount Rainier)
# ---------------------------------------------------------------------------
#
# Layout (64×32):
#   y=0-7    local time at the weather location (4×6, centred)
#   y=8-31   sun/moon on a half-circle arch, drawn BEFORE the mountains so it
#            rises from and sets behind them
#
_ARC_X0, _ARC_X1 = 5, 58  # horizontal travel (left horizon -> right horizon)
_ARC_Y_HORIZON = 29  # centre y at sunrise/sunset (hidden behind the ground)
_ARC_Y_PEAK = 11  # centre y at solar noon (just clears the summit)
_BODY_R = 3
_GROUND_TOP = 25  # y of the first ground row
_STARS = [(3, 11), (11, 9), (20, 12), (42, 9), (52, 14), (60, 9)]

# Mount Rainier, as seen from Seattle: a broad glaciated dome with the Liberty
# Cap shoulder on the left and the rocky Little Tahoma spur on the right.
# website/src/pages/weather/SkyCard.js mirrors these numbers — keep in sync.
_RAINIER = [  # (x, top y) outline points, joined by straight lines
    (0, 25),
    (2, 25),
    (8, 23),
    (14, 21),
    (19, 19),
    (23, 17),
    (26, 16),
    (28, 15),
    (30, 14),
    (35, 14),
    (38, 15),
    (41, 17),
    (42, 18),
    (44, 17),
    (46, 19),
    (50, 21),
    (55, 23),
    (61, 25),
    (63, 25),
]
_SNOW_LINE = 20  # snow covers everything above this row...
_GLACIERS = {15: 22, 16: 23, 21: 22, 25: 21, 31: 21, 39: 22, 40: 23, 48: 22}
_BARE_ROCK = {(44, 17), (43, 18), (44, 18), (45, 18)}  # Little Tahoma
_SHADE_FROM_X = 33  # snow right of the summit is in shadow
_TREELINE = 23  # forest on the low slopes from this row down

_C_SNOW = (210, 220, 235)
_C_SNOW_SHADE = (150, 165, 195)
_C_ROCK = (75, 80, 105)
_C_FOREST = (25, 60, 40)
_C_GROUND = (15, 38, 28)


def _rainier_top(x: int) -> int:
    for (x0, y0), (x1, y1) in zip(_RAINIER, _RAINIER[1:]):
        if x0 <= x <= x1:
            return round(y0 + (y1 - y0) * (x - x0) / (x1 - x0))
    return _GROUND_TOP


def _rainier_pixel(x: int, y: int):
    """Colour of the mountain/ground at (x, y), or None for open sky."""
    if y < _rainier_top(x):
        return None
    if y >= _GROUND_TOP:
        return _C_GROUND
    snow_bottom = max(_SNOW_LINE, _GLACIERS.get(x, 0))
    if y < snow_bottom and (x, y) not in _BARE_ROCK:
        return _C_SNOW_SHADE if x >= _SHADE_FROM_X else _C_SNOW
    if y >= _TREELINE:
        return _C_FOREST
    return _C_ROCK


def _put(canvas, x: int, y: int, rgb) -> None:
    if 0 <= x < MATRIX_W and 0 <= y < MATRIX_H:
        canvas.SetPixel(x, y, *rgb)


def _draw_sun(canvas, cx: int, cy: int) -> None:
    for dy in range(-_BODY_R, _BODY_R + 1):
        for dx in range(-_BODY_R, _BODY_R + 1):
            if dx * dx + dy * dy <= 10:
                _put(canvas, cx + dx, cy + dy, (255, 200, 0))


def _draw_moon(canvas, cx: int, cy: int, phase: float) -> None:
    c = math.cos(2 * math.pi * phase)  # 1 new, 0 quarter, -1 full
    waxing = phase < 0.5
    for dy in range(-_BODY_R, _BODY_R + 1):
        w = math.sqrt(max(0.0, 10.5 - dy * dy))
        for dx in range(-_BODY_R, _BODY_R + 1):
            if dx * dx + dy * dy > 10:
                continue
            # Lit side is the right in the first half of the cycle, left after.
            lit = dx >= w * c - 0.01 if waxing else dx <= -w * c + 0.01
            _put(canvas, cx + dx, cy + dy, (225, 230, 245) if lit else (45, 50, 70))


def _draw_mountains(canvas, night: bool) -> None:
    dim = 0.5 if night else 1.0
    for x in range(MATRIX_W):
        for y in range(_rainier_top(x), MATRIX_H):
            r, g, b = _rainier_pixel(x, y)
            _put(canvas, x, y, (int(r * dim), int(g * dim), int(b * dim)))


def render_sky(canvas, data: dict) -> bool:
    """Draw the sky screen. Returns False (nothing drawn) when sun times are
    unavailable, so the caller can skip this screen."""
    pos = sky_mod.compute(data.get("sky"))
    if pos is None:
        return False

    _clear(canvas)
    now = pos["local_now"]
    h = now.hour % 12 or 12
    ampm = "A" if now.hour < 12 else "P"
    time_str = f"{h}:{now.strftime('%M')}{ampm}"
    _draw_text(
        canvas,
        time_str,
        x=(MATRIX_W - len(time_str) * _CW_SMALL) // 2,
        baseline_y=7,
        color=_color(255, 255, 255),
        font="small",
    )

    p = pos["progress"]
    cx = round(_ARC_X0 + p * (_ARC_X1 - _ARC_X0))
    cy = round(_ARC_Y_HORIZON - (_ARC_Y_HORIZON - _ARC_Y_PEAK) * math.sin(math.pi * p))

    if pos["body"] == "moon":
        for sx, sy in _STARS:
            _put(canvas, sx, sy, (90, 95, 120))
        _draw_moon(canvas, cx, cy, pos["phase"])
    else:
        _draw_sun(canvas, cx, cy)

    _draw_mountains(canvas, night=pos["body"] == "moon")  # last: sun/moon set behind it
    return True
