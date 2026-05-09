from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from scaler import downsample, normalize
from matrix import USING_HARDWARE

MATRIX_W = 64
MATRIX_H = 32

# DrawText y = baseline of glyph.
# 6x10 font (10px tall): baseline y=10 → chars in rows 0-9
# 5x8  font (8px tall):  baseline y=19 → chars in rows 11-18 (1px gap after row 0)
#
# Layout:
#   Row 0 (large, y=10): stock name left | current price right (small, y=8)
#   Row 1 (small, y=19): period label left | triangle + change cycling right
#   Chart: rows 20-31

ROW0_LARGE_Y = 10
ROW0_SMALL_Y = 8
ROW1_Y = 19
TRIANGLE_Y = ROW1_Y - 7  # top of the 5×5 triangle box, centred in 8px char height
TRIANGLE_W = 5
TRIANGLE_GAP = 1  # px between triangle and text

CHART_TOP = 20
CHART_H = MATRIX_H - CHART_TOP

_FONT_DIR = Path(__file__).parent.parent / "fonts"
_BDF_LARGE = _FONT_DIR / "6x10.bdf"
_BDF_SMALL = _FONT_DIR / "5x8.bdf"
_CHAR_W_LARGE = 6
_CHAR_W_SMALL = 5

COLOR_UP = (0, 255, 0)
COLOR_DOWN = (255, 0, 0)
COLOR_NEUTRAL = (255, 255, 255)
COLOR_TEXT = (255, 255, 255)
COLOR_LABEL = (180, 180, 180)
COLOR_BG = (0, 0, 0)

_PERIOD_SHORT = {
    "Today": "1D",
    "6 Months": "6M",
    "Year to Date": "YTD",
    "1 Year": "1Y",
}

# Hardware fonts
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

# PIL fallback fonts for mock mode
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


def _twl(text: str) -> int:
    return len(text) * _CHAR_W_LARGE


def _tws(text: str) -> int:
    return len(text) * _CHAR_W_SMALL


def _draw_triangle(img: Image.Image, x: int, y: int, up: bool, color: tuple) -> None:
    """
    Draw a 5×5 pixel triangle into img at top-left (x, y).

    up=True:          up=False:
      00x00             00000
      0xxx0             00000
      xxxxx             xxxxx
      00000             0xxx0
      00000             00x00
    """
    if up:
        img.putpixel((x + 2, y + 0), color)
        for dx in (1, 2, 3):
            img.putpixel((x + dx, y + 1), color)
        for dx in range(5):
            img.putpixel((x + dx, y + 2), color)
    else:
        for dx in range(5):
            img.putpixel((x + dx, y + 2), color)
        for dx in (1, 2, 3):
            img.putpixel((x + dx, y + 3), color)
        img.putpixel((x + 2, y + 4), color)


def _dollar_change(data: dict) -> float | None:
    price = data.get("current_price")
    pct = data.get("change_pct")
    if price is None or pct is None:
        return None
    return price - price / (1 + pct / 100)


def render(canvas, data: dict, show_pct: bool = True) -> None:
    symbol = data.get("symbol", "----")
    price = data.get("current_price")
    pct = data.get("change_pct")
    direction = data.get("direction")
    closes = data.get("closes", [])
    label = data.get("label", "")
    dollar = _dollar_change(data)
    up = direction == "up"
    neutral = direction not in ("up", "down")

    direction_color = (
        COLOR_UP
        if direction == "up"
        else COLOR_DOWN if direction == "down" else COLOR_NEUTRAL
    )

    short_label = _PERIOD_SHORT.get(label, label)
    price_str = f"${price:.2f}" if price is not None else ""
    pct_str = f"{abs(pct):.2f}%" if pct is not None else ""
    dollar_str = f"${abs(dollar):.2f}" if dollar is not None else ""
    change_str = pct_str if show_pct else dollar_str

    # Triangle + change block width (used for right-alignment)
    change_block_w = (
        (TRIANGLE_W + TRIANGLE_GAP + _tws(change_str))
        if change_str and not neutral
        else _tws(change_str)
    )
    triangle_x = MATRIX_W - change_block_w
    change_x = triangle_x + TRIANGLE_W + TRIANGLE_GAP

    # Build image: chart pixels in bottom rows, header stays black
    img = Image.new("RGB", (MATRIX_W, MATRIX_H), COLOR_BG)
    if closes:
        bars = downsample(closes, MATRIX_W)
        heights = normalize(bars, CHART_H)
        for x, h in enumerate(heights):
            for y in range(h):
                row = MATRIX_H - 1 - y
                if row >= CHART_TOP:
                    img.putpixel((x, row), direction_color)

    # Draw triangle into PIL image (works for both hardware and mock)
    if change_str and not neutral:
        _draw_triangle(img, triangle_x, TRIANGLE_Y, up, direction_color)

    if USING_HARDWARE and _gfx and _hw_large and _hw_small:
        canvas.SetImage(img)

        tc = _gfx.Color(*COLOR_TEXT)
        lc = _gfx.Color(*COLOR_LABEL)
        dc = _gfx.Color(*direction_color)

        _gfx.DrawText(canvas, _hw_large, 0, ROW0_LARGE_Y, tc, symbol)

        if price_str:
            _gfx.DrawText(
                canvas,
                _hw_small,
                MATRIX_W - _tws(price_str),
                ROW0_SMALL_Y,
                dc,
                price_str,
            )

        _gfx.DrawText(canvas, _hw_small, 0, ROW1_Y, lc, short_label)

        if change_str:
            _gfx.DrawText(canvas, _hw_small, change_x, ROW1_Y, dc, change_str)

    else:
        # Mock / fallback: PIL text
        draw = ImageDraw.Draw(img)

        draw.text((0, 0), symbol, font=_pil_large, fill=COLOR_TEXT)

        if price_str:
            pw = round(draw.textlength(price_str, font=_pil_small))
            draw.text(
                (MATRIX_W - pw, 0), price_str, font=_pil_small, fill=direction_color
            )

        draw.text((0, 9), short_label, font=_pil_small, fill=COLOR_LABEL)

        if change_str:
            cw = round(draw.textlength(change_str, font=_pil_small))
            draw.text(
                (MATRIX_W - cw, 9), change_str, font=_pil_small, fill=direction_color
            )

        canvas.SetImage(img)
