"""
Weather display renderer — three cycling screens on the 64×32 RGB matrix.

Screen 1 (current):   large icon + temperature + feels-like + condition + city
Screen 2 (hourly):    6 columns — time label / icon / temp
Screen 3 (forecast):  5 columns — day / icon / hi / lo
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

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
