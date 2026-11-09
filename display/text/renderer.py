import colorsys
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw

import bdf as _bdf

MATRIX_W = 64
MATRIX_H = 32
COLOR_BG = (0, 0, 0)

_FONT_DIR = Path(__file__).parent.parent / "fonts"

# Font file, cell height, ascent (baseline offset from the cell top), letter width.
_FONT_LARGE = ("6x10.bdf", 10, 8, 6)
_FONT_MEDIUM = ("5x8.bdf", 8, 7, 5)
_FONT_SMALL = ("4x6.bdf", 6, 5, 4)

# Row count -> (font, y of each row's top). Rows are spaced evenly down the 32px
# height; one row sits in the middle and five rows fill it.
LAYOUTS = {
    1: (_FONT_LARGE, [11]),
    2: (_FONT_LARGE, [4, 18]),
    3: (_FONT_MEDIUM, [2, 12, 22]),
    4: (_FONT_SMALL, [1, 9, 17, 25]),
    5: (_FONT_SMALL, [1, 7, 13, 19, 25]),
}

# Parsed at import: the matrix library drops root once it starts, and the user
# it drops to can't read files under /home/pi. bdf.load caches each font.
for _font_spec in (_FONT_LARGE, _FONT_MEDIUM, _FONT_SMALL):
    _bdf.load(_FONT_DIR / _font_spec[0])

_SCROLL_GAP = 16  # blank pixels between the end of a scrolling row and its repeat
_RAINBOW_CYCLES = 1.5  # full hue cycles across the 64px width, same as Clock


@lru_cache(maxsize=32)
def _text_mask(font_spec: tuple, text: str) -> Image.Image:
    """White-on-black strip of the whole row, reused between frames."""
    file_name, height, ascent, _ = font_spec
    font = _bdf.load(_FONT_DIR / file_name)
    width = sum(
        font.glyphs[ord(ch)].dwidth if ord(ch) in font.glyphs else font.default_dwidth
        for ch in text
    )
    mask = Image.new("L", (max(1, width), height), 0)
    font.draw(ImageDraw.Draw(mask), 0, ascent, text, 255)
    return mask


def _rainbow_strip(height: int, phase: float) -> Image.Image:
    """One hue per x-column; subtracting `phase` slides the hues to the right."""
    strip = Image.new("RGB", (MATRIX_W, 1))
    for x in range(MATRIX_W):
        hue = ((x / MATRIX_W) * _RAINBOW_CYCLES - phase) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        strip.putpixel((x, 0), (int(r * 255), int(g * 255), int(b * 255)))
    return strip.resize((MATRIX_W, height), Image.NEAREST)


def _visible_mask(strip: Image.Image, row: dict, scroll_px: int) -> tuple:
    """Return (64px wide mask of what's on the board, whether the row scrolls)."""
    visible = Image.new("L", (MATRIX_W, strip.height), 0)
    if strip.width > MATRIX_W and row.get("scroll", True):
        period = strip.width + _SCROLL_GAP
        offset = scroll_px % period
        visible.paste(strip, (-offset, 0))
        visible.paste(strip, (period - offset, 0))
        return visible, True

    # Fits, or scrolling is off and the row is cut off at the board's edges.
    align = row.get("align", "center")
    x = 0
    if align == "center":
        x = (MATRIX_W - strip.width) // 2
    elif align == "right":
        x = MATRIX_W - strip.width
    visible.paste(strip, (x, 0))
    return visible, False


def render(
    canvas,
    row_count: int,
    rows: list,
    scroll_seconds: int,
    elapsed: float,
    phase: float,
) -> bool:
    """Draw the rows. Returns True if anything on the board is moving."""
    font_spec, tops = LAYOUTS.get(row_count, LAYOUTS[1])
    height = font_spec[1]
    scroll_px = int(elapsed * font_spec[3] / scroll_seconds)
    frame = Image.new("RGB", (MATRIX_W, MATRIX_H), COLOR_BG)
    animated = False

    for top, row in zip(tops, rows):
        text = row.get("text", "")
        if not text:
            continue
        strip = _text_mask(font_spec, text)
        visible, scrolling = _visible_mask(strip, row, scroll_px)
        if row.get("color_mode") == "rainbow":
            frame.paste(_rainbow_strip(height, phase), (0, top), visible)
            animated = True
        else:
            color = tuple(row.get("color", [255, 255, 255]))
            frame.paste(color, (0, top, MATRIX_W, top + height), visible)
        animated = animated or scrolling

    canvas.SetImage(frame)
    return animated
