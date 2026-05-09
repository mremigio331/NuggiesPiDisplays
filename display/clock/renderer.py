from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from matrix import USING_HARDWARE

MATRIX_W = 64
MATRIX_H = 32

_FONT_DIR = Path(__file__).parent.parent / "fonts"
_BDF_LARGE = _FONT_DIR / "6x10.bdf"
_BDF_SMALL = _FONT_DIR / "5x8.bdf"
_CHAR_W_LARGE = 6
_CHAR_W_SMALL = 5

# 6x10 font baseline=13 → glyphs fill rows 3–12 (vertically centered in top half)
# 5x8  font baseline=26 → glyphs fill rows 18–25 (centered in bottom half)
TIME_Y = 13
DATE_Y = 26
COLOR_BG = (0, 0, 0)

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

try:
    _pil_large = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10
    )
    _pil_small = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8
    )
except OSError:
    _pil_large = ImageFont.load_default()
    _pil_small = _pil_large


def _center_x(text: str, char_w: int) -> int:
    return max(0, (MATRIX_W - len(text) * char_w) // 2)


def render(canvas, dt: datetime, color: tuple, use_24h: bool = False) -> None:
    if use_24h:
        time_str = dt.strftime("%H:%M:%S")  # e.g. "15:45:30"
    else:
        time_str = dt.strftime(
            "%-I:%M:%S%p"
        )  # e.g. "3:45:30PM" (no space keeps it within 64px)
    date_str = dt.strftime("%a %b %d")  # e.g. "Mon Jan 06"

    time_x = _center_x(time_str, _CHAR_W_LARGE)
    date_x = _center_x(date_str, _CHAR_W_SMALL)

    img = Image.new("RGB", (MATRIX_W, MATRIX_H), COLOR_BG)

    if USING_HARDWARE and _gfx and _hw_large and _hw_small:
        canvas.SetImage(img)
        c = _gfx.Color(*color)
        _gfx.DrawText(canvas, _hw_large, time_x, TIME_Y, c, time_str)
        _gfx.DrawText(canvas, _hw_small, date_x, DATE_Y, c, date_str)
    else:
        draw = ImageDraw.Draw(img)
        draw.text((time_x, TIME_Y - 10), time_str, font=_pil_large, fill=color)
        draw.text((date_x, DATE_Y - 8), date_str, font=_pil_small, fill=color)
        canvas.SetImage(img)
