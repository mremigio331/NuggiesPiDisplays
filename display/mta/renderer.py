from pathlib import Path
from matrix import USING_HARDWARE

MATRIX_W = 64
MATRIX_H = 32

# Layout — maps the RIGHT HALF of the original 128px display onto our 64px panel.
# Original offsets:  circle x=64, letter x=67, direction x=74, time x=109/112
# Ours (subtract 64): circle x=0,  letter x=3,  direction x=10, time x=45/48
#
#  y=0-7   : station name (baseline y=7)
#  y=9-17  : train 1 circle + text (baseline y=17)
#  y=19-27 : train 2 circle + text (baseline y=27)

STATION_Y = 7
TRAIN_Y = [17, 27]
CIRCLE_Y = [9, 19]
CIRCLE_TOP = [10, 20]  # original: local_train(canvas, 64, 10, ...) and (64, 20, ...)
LETTER_X = 3  # original x=67, minus 64
DIR_X = 10  # original x=74,  minus 64
CHAR_W = 4  # 4x6 font

# Window sizes from original (chars visible in direction field)
WIN_ARRIVING = 13  # when train_time == 0: 13-char window
WIN_WAITING = 8  # when train_time  > 0:  8-char window

_gfx = None
_hw_font = None

if USING_HARDWARE:
    try:
        from rgbmatrix import graphics as _gfx

        _hw_font = _gfx.Font()
        _font_path = Path(__file__).parent.parent / "fonts" / "4x6.bdf"
        if _font_path.exists():
            _hw_font.LoadFont(str(_font_path))
    except Exception:
        _gfx = None

# MTA line colours — exact match to original pi_subway_ticker.py train_colors()
_LINE_COLORS = {
    "A": (0, 57, 166),
    "C": (0, 57, 166),
    "E": (0, 57, 166),
    "H": (0, 57, 166),
    "B": (255, 99, 25),
    "D": (255, 99, 25),
    "F": (255, 99, 25),
    "FX": (255, 99, 25),
    "M": (255, 99, 25),
    "G": (108, 190, 69),
    "GS": (108, 190, 69),
    "J": (153, 102, 51),
    "Z": (153, 102, 51),
    "L": (167, 169, 172),
    "N": (252, 204, 10),
    "Q": (252, 204, 10),
    "R": (252, 204, 10),
    "W": (252, 204, 10),
    "S": (128, 129, 131),
    "FS": (128, 129, 131),
    "1": (238, 53, 46),
    "2": (238, 53, 46),
    "3": (238, 53, 46),
    "4": (0, 147, 60),
    "5": (0, 147, 60),
    "6": (0, 147, 60),
    "6X": (0, 147, 60),
    "7": (185, 51, 173),
    "7X": (185, 51, 173),
    "T": (0, 173, 208),
    "SI": (149, 153, 160),
    "SIR": (149, 153, 160),
}

_COLOR_BLACK = (0, 0, 0)
_COLOR_WHITE = (255, 255, 255)
_COLOR_GREEN = (0, 147, 60)  # waiting_color
_COLOR_ORANGE = (237, 132, 40)  # arrival_color
_COLOR_RED = (238, 53, 46)


def _hw_color(rgb: tuple):
    return _gfx.Color(*rgb)


def _draw_circle(canvas, x: int, y: int, color):
    lines = [(2, 6), (1, 7), (0, 8), (0, 8), (0, 8), (0, 8), (0, 8), (1, 7), (2, 6)]
    for row, (lo, hi) in enumerate(lines):
        _gfx.DrawLine(canvas, x + lo, y + row, x + hi, y + row, color)


def _draw_diamond(canvas, x: int, y: int, color):
    lines = [(4, 4), (3, 5), (2, 6), (1, 7), (0, 8), (1, 7), (2, 6), (3, 5), (4, 4)]
    for row, (lo, hi) in enumerate(lines):
        _gfx.DrawLine(canvas, x + lo, y + row, x + hi, y + row, color)


def _draw_train_row(canvas, row_idx: int, train: dict, char_offset: int) -> None:
    route = train.get("route", "")
    mins = train.get("arrival_minutes", "")
    dest = train.get("destination", "")

    arriving = isinstance(mins, int) and mins == 0
    line_color = _hw_color(_LINE_COLORS.get(route, _COLOR_WHITE))
    black = _hw_color(_COLOR_BLACK)
    green = _hw_color(_COLOR_GREEN)
    orange = _hw_color(_COLOR_ORANGE)
    text_color = orange if arriving else green

    cy = CIRCLE_TOP[row_idx]
    ty = TRAIN_Y[row_idx]

    # Circle / diamond — single char = local (circle), multi = express (diamond)
    if len(route) == 1:
        _draw_circle(canvas, 0, cy, line_color)
    else:
        _draw_diamond(canvas, 0, cy, line_color)

    if route:
        _gfx.DrawText(canvas, _hw_font, LETTER_X, ty, black, route[0])

    # Time — only when NOT arriving, right-aligned (original x=112 or 109, minus 64)
    if not arriving and isinstance(mins, int):
        time_str = f"{mins}min"
        time_x = 48 if len(time_str) == 4 else 45
        _gfx.DrawText(canvas, _hw_font, time_x, ty, green, time_str)

    # Direction — windowed + character-based scroll (matching original add_number logic)
    window = WIN_ARRIVING if arriving else WIN_WAITING
    if len(dest) > window:
        print_text = dest[char_offset : char_offset + window]
    else:
        print_text = dest
    _gfx.DrawText(canvas, _hw_font, DIR_X, ty, text_color, print_text)


def _draw_logo_row(canvas, lines: list) -> None:
    """6 static train circles, refreshed every second while in error state."""
    cy = 16
    black = _hw_color(_COLOR_BLACK)
    for i, line in enumerate(lines[:6]):
        cx = 2 + i * 10
        color = _hw_color(_LINE_COLORS.get(line, _COLOR_WHITE))
        if len(line) == 1:
            _draw_circle(canvas, cx, cy, color)
        else:
            _draw_diamond(canvas, cx, cy, color)
        if line:
            _gfx.DrawText(canvas, _hw_font, cx + 3, cy + 7, black, line[0])


def render(
    canvas,
    station_name: str,
    trains: list,
    station_scroll_x: int = 0,
    dest_char_offsets: list | None = None,
    api_error: bool = False,
    show_loading: bool = False,
    loading_lines: list | None = None,
) -> None:
    if not USING_HARDWARE or not _gfx or not _hw_font:
        return

    offsets = dest_char_offsets or [0, 0]
    canvas.Clear()

    if api_error:
        _gfx.DrawText(
            canvas, _hw_font, 0, STATION_Y, _hw_color(_COLOR_RED), "API Error"
        )
        _draw_logo_row(canvas, loading_lines or [])
        return

    if show_loading:
        _draw_logo_row(canvas, loading_lines or [])
        return

    green = _hw_color(_COLOR_GREEN)
    name_w = len(station_name) * CHAR_W
    if name_w > MATRIX_W:
        scroll_range = name_w - MATRIX_W
        PAUSE = 20  # hold at each end for 20 * SCROLL_STEP_S ≈ 3 s
        period = PAUSE + scroll_range + PAUSE
        pos = station_scroll_x % period
        if pos < PAUSE:
            sx = 0
        elif pos < PAUSE + scroll_range:
            sx = -(pos - PAUSE)
        else:
            sx = -scroll_range
    else:
        sx = 0
    _gfx.DrawText(canvas, _hw_font, sx, STATION_Y, green, station_name)

    for i, train in enumerate(trains[:2]):
        _draw_train_row(canvas, i, train, offsets[i])
