import colorsys
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw
from matrix import USING_HARDWARE

MATRIX_W = 64
MATRIX_H = 32

_FONT_DIR = Path(__file__).parent.parent / "fonts"
_BDF_LARGE = _FONT_DIR / "6x10.bdf"
_BDF_SMALL = _FONT_DIR / "5x8.bdf"
_BDF_TINY = _FONT_DIR / "4x6.bdf"
_CHAR_W_LARGE = 6
_CHAR_W_SMALL = 5
_CHAR_W_TINY = 4

# Focus view: three centered lines stacked over the 32px height.
#   time (6x10) baseline=10 -> rows ~1-10
#   date (5x8)  baseline=20 -> rows ~13-20
#   tz   (5x8)  baseline=30 -> rows ~23-30
FOCUS_TIME_Y = 10
FOCUS_DATE_Y = 20
FOCUS_TZ_Y = 30
COLOR_BG = (0, 0, 0)

# Rainbow ("Caitlin Mode"): how many full hue cycles span the 64px width.
_RAINBOW_CYCLES = 1.5

_gfx = None
_hw_large = None
_hw_small = None
_hw_tiny = None
if USING_HARDWARE:
    try:
        from rgbmatrix import graphics as _gfx

        if _BDF_LARGE.exists():
            _hw_large = _gfx.Font()
            _hw_large.LoadFont(str(_BDF_LARGE))
        if _BDF_SMALL.exists():
            _hw_small = _gfx.Font()
            _hw_small.LoadFont(str(_BDF_SMALL))
        if _BDF_TINY.exists():
            _hw_tiny = _gfx.Font()
            _hw_tiny.LoadFont(str(_BDF_TINY))
    except Exception:
        _gfx = None

# Bitmap fonts for the PIL mask path (rainbow + headless mock). Parsed from the
# same BDF files the hardware uses, so text looks identical to the solid path.
import bdf as _bdf

_mask_large = _bdf.load(_BDF_LARGE)
_mask_small = _bdf.load(_BDF_SMALL)
_mask_tiny = _bdf.load(_BDF_TINY)


def _center_x(text: str, char_w: int) -> int:
    return max(0, (MATRIX_W - len(text) * char_w) // 2)


def _tz_abbr(dt: datetime, tz_name: str) -> str:
    """Short label for a zone: its %Z abbreviation, or a slice of the IANA
    city name if the abbreviation is numeric/empty (e.g. '+05')."""
    abbr = dt.strftime("%Z")
    if not abbr or any(ch.isdigit() for ch in abbr):
        abbr = tz_name.split("/")[-1][:4].upper()
    return abbr


# --- Rainbow ("Caitlin Mode") ----------------------------------------------- #


def _rainbow_columns(phase: float):
    """Precompute one (r, g, b) per x-column for the current animation phase.

    `phase` advances over time; subtracting it shifts the hue pattern to the
    right (a column shows the hue that was just to its left a moment ago)."""
    cols = []
    for x in range(MATRIX_W):
        hue = ((x / MATRIX_W) * _RAINBOW_CYCLES - phase) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        cols.append((int(r * 255), int(g * 255), int(b * 255)))
    return cols


def _colorize(img: Image.Image, color, rainbow_phase):
    """Return `img` (white-on-black text mask) recolored.

    Solid: every lit pixel becomes `color`. Rainbow: each lit pixel takes the
    hue of its x-column for `rainbow_phase`."""
    out = Image.new("RGB", img.size, COLOR_BG)
    src = img.load()
    dst = out.load()
    w, h = img.size
    if rainbow_phase is None:
        for y in range(h):
            for x in range(w):
                if src[x, y][0] > 40:  # lit pixel in the mask
                    dst[x, y] = color
    else:
        cols = _rainbow_columns(rainbow_phase)
        for y in range(h):
            for x in range(w):
                if src[x, y][0] > 40:
                    dst[x, y] = cols[x]
    return out


_MASK_FONTS = {"large": _mask_large, "small": _mask_small, "tiny": _mask_tiny}


def _draw_mask(lines):
    """Draw `lines` [(x, baseline_y, text, font_key)] as a white-on-black mask,
    using the BDF bitmap fonts so glyphs match the hardware solid path."""
    mask = Image.new("RGB", (MATRIX_W, MATRIX_H), COLOR_BG)
    draw = ImageDraw.Draw(mask)
    for x, baseline_y, text, key in lines:
        _MASK_FONTS[key].draw(draw, x, baseline_y, text, (255, 255, 255))
    return mask


def render(
    canvas,
    dt: datetime,
    color: tuple,
    use_24h: bool = False,
    tz_name: str = "",
    rainbow_phase=None,
) -> None:
    """Focus view: one timezone, three centered lines (time / date / tz)."""
    if use_24h:
        time_str = dt.strftime("%H:%M:%S")  # e.g. "15:45:30"
    else:
        time_str = dt.strftime("%-I:%M:%S%p")  # e.g. "3:45:30PM" (no space fits 64px)
    date_str = dt.strftime("%a %b %d")  # e.g. "Mon Jan 06"
    tz_str = _tz_abbr(dt, tz_name)

    time_x = _center_x(time_str, _CHAR_W_LARGE)
    date_x = _center_x(date_str, _CHAR_W_SMALL)
    tz_x = _center_x(tz_str, _CHAR_W_SMALL)

    # Hardware with solid color uses the crisp BDF glyph path. Rainbow (and the
    # headless mock) go through the PIL mask + per-pixel colorize path.
    if USING_HARDWARE and _gfx and _hw_large and _hw_small and rainbow_phase is None:
        canvas.SetImage(Image.new("RGB", (MATRIX_W, MATRIX_H), COLOR_BG))
        c = _gfx.Color(*color)
        _gfx.DrawText(canvas, _hw_large, time_x, FOCUS_TIME_Y, c, time_str)
        _gfx.DrawText(canvas, _hw_small, date_x, FOCUS_DATE_Y, c, date_str)
        _gfx.DrawText(canvas, _hw_small, tz_x, FOCUS_TZ_Y, c, tz_str)
        return

    mask = _draw_mask(
        [
            (time_x, FOCUS_TIME_Y, time_str, "large"),
            (date_x, FOCUS_DATE_Y, date_str, "small"),
            (tz_x, FOCUS_TZ_Y, tz_str, "small"),
        ]
    )
    canvas.SetImage(_colorize(mask, color, rainbow_phase))


# --- Multi view (up to three timezones) ------------------------------------- #
# The 64px width is divided into three equal columns (~21px each). Each column
# shows, top to bottom: the timezone abbreviation, the time (H:MM), and AM/PM.
# A thin vertical divider separates the columns. Everything uses the 4x6 tiny
# font so a 5-char time ("12:59" = 20px) fits inside a column.

_COL_COUNT = 3
_COL_W = MATRIX_W // _COL_COUNT  # 21px

_W_ABBR_Y = 7  # tz abbreviation (rows ~2-6)
_W_TIME_Y = 19  # time (rows ~14-18)
_W_AMPM_Y = 29  # AM/PM (rows ~24-28)


def _col_center_x(col: int, text: str, char_w: int) -> int:
    """Center `text` horizontally within column `col` (0-indexed)."""
    col_left = col * _COL_W
    inner = max(0, (_COL_W - len(text) * char_w) // 2)
    x = col_left + inner
    return max(0, min(x, MATRIX_W - len(text) * char_w))


def render_multi(
    canvas, entries: list, color: tuple, use_24h: bool = False, rainbow_phase=None
) -> None:
    """Render up to three timezone columns.

    `entries` is a list of (abbr, datetime) tuples in display order, sliced to
    at most 3 by the caller.
    """
    lines = []  # (x, baseline_y, text)
    for i, (abbr, dt) in enumerate(entries[:_COL_COUNT]):
        if use_24h:
            time_str = dt.strftime("%H:%M")
            ampm_str = ""
        else:
            time_str = dt.strftime("%-I:%M")  # e.g. "1:05"
            ampm_str = dt.strftime("%p")  # "AM" / "PM"

        abbr = (abbr or "")[:4]

        lines.append((_col_center_x(i, abbr, _CHAR_W_TINY), _W_ABBR_Y, abbr))
        lines.append((_col_center_x(i, time_str, _CHAR_W_TINY), _W_TIME_Y, time_str))
        if ampm_str:
            lines.append(
                (_col_center_x(i, ampm_str, _CHAR_W_TINY), _W_AMPM_Y, ampm_str)
            )

    divider_cols = range(1, min(len(entries), _COL_COUNT))

    if USING_HARDWARE and _gfx and _hw_tiny and rainbow_phase is None:
        canvas.SetImage(Image.new("RGB", (MATRIX_W, MATRIX_H), COLOR_BG))
        c = _gfx.Color(*color)
        divider = _gfx.Color(*[v // 3 for v in color])
        for col in divider_cols:
            x = col * _COL_W
            _gfx.DrawLine(canvas, x, 0, x, MATRIX_H - 1, divider)
        for x, y, text in lines:
            _gfx.DrawText(canvas, _hw_tiny, x, y, c, text)
        return

    # PIL mask path (headless mock, or rainbow on hardware).
    mask = _draw_mask([(x, y, text, "tiny") for (x, y, text) in lines])
    img = _colorize(mask, color, rainbow_phase)
    # Draw dividers after colorizing so they stay a dim constant tone.
    draw = ImageDraw.Draw(img)
    div_color = tuple(v // 3 for v in color) if rainbow_phase is None else (60, 60, 60)
    for col in divider_cols:
        x = col * _COL_W
        draw.line([(x, 0), (x, MATRIX_H - 1)], fill=div_color)
    canvas.SetImage(img)
