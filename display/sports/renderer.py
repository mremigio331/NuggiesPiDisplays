"""
Basketball display renderer — 64×32 RGB matrix.

Layout:
  Left panel  (x=0..27, 28px):
    Away section (y=0..9):    team-color bg, white team abbr + score (2px pad each side)
    Home section (y=10..19):  team-color bg, white team abbr + score (2px pad each side)
    Status zone  (y=20..31):  black bg, Q3 4:42 / Final / tip time
  Divider     (x=28):         dim vertical line, full height
  Right panel (x=29..63, 35px): cycles every 15s between —
    "players" view: top 5 scorers (both teams), jersey # + pts, colored by team
    "fouls"   view: top 4 scorers with personal foul counts + team foul totals

Colors:
  Left backgrounds: team color normalized to _BG_PEAK brightness so white text
                    is always legible regardless of team color.
  Right text:       team color boosted to _MIN_BRIGHTNESS floor for text legibility.
  Foul counts:      green→yellow→orange→red as fouls accumulate.
"""

import time
from datetime import datetime
from pathlib import Path
from matrix import USING_HARDWARE

MATRIX_W = 64
MATRIX_H = 32
LEFT_W = 28  # left panel pixel width (x=0..27)
DIVIDER_X = 28  # vertical divider column
RIGHT_X = 29  # right panel start
RIGHT_W = 35  # right panel pixel width (x=29..63)

_FONT_DIR = Path(__file__).parent.parent / "fonts"
_BDF_SM = _FONT_DIR / "4x6.bdf"
_CW = 4  # character width for 4x6 font
_CH = 6  # character height

_gfx = _hw_sm = None
if USING_HARDWARE:
    try:
        from rgbmatrix import graphics as _gfx

        if _BDF_SM.exists():
            _hw_sm = _gfx.Font()
            _hw_sm.LoadFont(str(_BDF_SM))
    except Exception:
        _gfx = None

try:
    from PIL import ImageFont

    _pil_sm = ImageFont.load_default()
except Exception:
    _pil_sm = None


_MIN_BRIGHTNESS = 120  # text: boost dark colors so they're legible
_BG_PEAK = 100  # background: normalize all team colors to this peak


def _color(r: int, g: int, b: int):
    return _gfx.Color(r, g, b) if _gfx else (r, g, b)


def _parse_hex(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _team_color(hex_str: str):
    """Team color for text — boosts dark colors to _MIN_BRIGHTNESS peak."""
    try:
        r, g, b = _parse_hex(hex_str)
    except Exception:
        return _color(200, 200, 200)
    peak = max(r, g, b)
    if peak == 0:
        return _color(200, 200, 200)
    if peak < _MIN_BRIGHTNESS:
        scale = _MIN_BRIGHTNESS / peak
        r, g, b = (
            min(255, int(r * scale)),
            min(255, int(g * scale)),
            min(255, int(b * scale)),
        )
    return _color(r, g, b)


def _team_bg_rgb(hex_str: str) -> tuple[int, int, int]:
    """Team color for background fill — normalized to _BG_PEAK so white text stays legible."""
    try:
        r, g, b = _parse_hex(hex_str)
    except Exception:
        return (40, 40, 40)
    peak = max(r, g, b)
    if peak == 0:
        return (40, 40, 40)
    scale = _BG_PEAK / peak
    return (
        min(255, int(r * scale)),
        min(255, int(g * scale)),
        min(255, int(b * scale)),
    )


def _team_color_rgb(hex_str: str) -> tuple[int, int, int]:
    """Team color as raw (r,g,b) ints — same brightness boost as _team_color."""
    try:
        r, g, b = _parse_hex(hex_str)
    except Exception:
        return (200, 200, 200)
    peak = max(r, g, b)
    if peak == 0:
        return (200, 200, 200)
    if peak < _MIN_BRIGHTNESS:
        scale = _MIN_BRIGHTNESS / peak
        r, g, b = (
            min(255, int(r * scale)),
            min(255, int(g * scale)),
            min(255, int(b * scale)),
        )
    return (r, g, b)


def _fill_rect(
    canvas, x0: int, y0: int, x1: int, y1: int, r: int, g: int, b: int
) -> None:
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            canvas.SetPixel(x, y, r, g, b)


def _draw_foul_bar(canvas, fouls: int, x_start: int, y: int) -> None:
    """Draw a 6-segment foul-progress bar (2px per segment) at the given position.

    Segments fill left-to-right as fouls accumulate:
      1-2 fouls → green, 3 → yellow, 4 → orange, 5-6 → red.
    Unfilled segments are drawn very dim so the bar shape is always visible.
    """
    _SEG_COLORS = [
        (0, 180, 60),  # foul 1 — green
        (0, 180, 60),  # foul 2 — green
        (220, 200, 0),  # foul 3 — yellow
        (255, 120, 0),  # foul 4 — orange
        (220, 40, 0),  # foul 5 — red (danger)
        (200, 0, 0),  # foul 6 — red (fouled out)
    ]
    _DIM = (22, 22, 22)
    for i in range(6):
        r, g, b = _SEG_COLORS[i] if fouls > i else _DIM
        x = x_start + i * 2
        canvas.SetPixel(x, y, r, g, b)
        canvas.SetPixel(x + 1, y, r, g, b)


def _draw_text(canvas, text: str, x: int, baseline_y: int, color) -> None:
    if _gfx and _hw_sm:
        _gfx.DrawText(canvas, _hw_sm, x, baseline_y, color, text)
    else:
        try:
            from PIL import ImageDraw

            draw = ImageDraw.Draw(canvas._image)
            draw.text((x, baseline_y - _CH), text, font=_pil_sm, fill=color)
        except Exception:
            pass


def _draw_divider(canvas) -> None:
    for y in range(MATRIX_H):
        canvas.SetPixel(DIVIDER_X, y, 40, 40, 40)


def _center_x(text: str, start_x: int, width: int) -> int:
    return start_x + max(0, (width - len(text) * _CW) // 2)


def _format_game_time(game_date: str) -> str:
    """Convert UTC ISO game_date to local 12-hour time string, e.g. '7:30p'."""
    if not game_date:
        return ""
    try:
        dt = datetime.fromisoformat(game_date.replace("Z", "+00:00")).astimezone()
        h = dt.hour % 12 or 12
        return f"{h}:{dt.minute:02d}{'a' if dt.hour < 12 else 'p'}"
    except Exception:
        return ""


def _draw_team_score_row(
    canvas,
    abbr: str,
    score,
    show_score: bool,
    bg_hex: str,
    text_color,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    baseline_y: int,
) -> None:
    """Fill a rect with team bg color, draw abbr at left, score right-aligned."""
    _fill_rect(canvas, x0, y0, x1, y1, *_team_bg_rgb(bg_hex))
    _draw_text(canvas, abbr, x0 + 1, baseline_y, text_color)
    if show_score:
        s = str(score)
        _draw_text(canvas, s, x1 - len(s) * _CW + 1, baseline_y, text_color)


def _render_focus_left_header(canvas, game: dict) -> str:
    """Draw away + home score rows in the focus left panel. Returns state."""
    state = game.get("state", "pre")
    away_tc = _team_color(game.get("away_alt_color", "ffffff"))
    home_tc = _team_color(game.get("home_alt_color", "ffffff"))
    _draw_team_score_row(
        canvas,
        game.get("away_team", "???")[:4],
        game.get("away_score", 0),
        state != "pre",
        game.get("away_color", "333333"),
        away_tc,
        0,
        0,
        LEFT_W - 1,
        9,
        7,
    )
    _draw_team_score_row(
        canvas,
        game.get("home_team", "???")[:4],
        game.get("home_score", 0),
        state != "pre",
        game.get("home_color", "333333"),
        home_tc,
        0,
        10,
        LEFT_W - 1,
        19,
        17,
    )
    return state


def _render_overview_panel_base(canvas, game: dict, x0: int, w: int) -> tuple[str, int]:
    """Draw away section + border + home section for any sport's overview panel.
    Returns (state, x1) for the caller's info strip."""
    state = game.get("state", "pre")
    x1 = x0 + w - 1
    away_tc = _team_color(game.get("away_alt_color", "ffffff"))
    home_tc = _team_color(game.get("home_alt_color", "ffffff"))
    _draw_team_score_row(
        canvas,
        game.get("away_team", "???")[:3],
        game.get("away_score", 0),
        state != "pre",
        game.get("away_color", "333333"),
        away_tc,
        x0,
        0,
        x1,
        9,
        7,
    )
    for x in range(x0, x0 + w):
        canvas.SetPixel(x, 10, 40, 40, 40)
    _draw_team_score_row(
        canvas,
        game.get("home_team", "???")[:3],
        game.get("home_score", 0),
        state != "pre",
        game.get("home_color", "333333"),
        home_tc,
        x0,
        11,
        x1,
        20,
        18,
    )
    return state, x1


def _draw_possession_column(canvas, game: dict) -> None:
    """Possession marker — 5px column at x=63, top for away / bottom for home."""
    possession = game.get("possession")
    if possession == "away":
        r, g, b = _team_color_rgb(game.get("away_color", "ffffff"))
        rows = range(0, 5)
    elif possession == "home":
        r, g, b = _team_color_rgb(game.get("home_color", "ffffff"))
        rows = range(27, 32)
    else:
        return
    for y in rows:
        canvas.SetPixel(MATRIX_W - 1, y, r, g, b)


def _foul_color(fouls: int):
    if fouls <= 2:
        return _color(0, 200, 80)  # green — safe
    if fouls <= 3:
        return _color(220, 200, 0)  # yellow — watch it
    if fouls == 4:
        return _color(255, 120, 0)  # orange — trouble
    if fouls == 5:
        return _color(255, 50, 0)  # red-orange — one more = out
    return _color(255, 0, 0)  # red — fouled out


def _render_left_panel(canvas, game: dict) -> None:
    state = _render_focus_left_header(canvas, game)
    period = game.get("period", 0)
    clock = game.get("clock", "")
    status_detail = game.get("status_detail", "")
    yellow = _color(255, 220, 0)
    gray = _color(160, 160, 160)

    # Status — centered in y=20..31, no background
    if state == "in":
        if period > 4:
            period_label = "OT" if period == 5 else f"OT{period - 4}"
        else:
            period_label = f"Q{period}"
        full_status = f"{period_label} {clock}" if clock else period_label
        while len(full_status) * _CW > LEFT_W and " " in full_status:
            full_status = full_status.rsplit(" ", 1)[0]
        status_col = yellow
    elif state == "post":
        if period == 5:
            full_status = "Fin OT"
        elif period > 5:
            full_status = f"Fn OT{period - 4}"
        else:
            full_status = "Final"
        status_col = gray
    else:
        full_status = (
            _format_game_time(game.get("game_date", "")) or status_detail or "Soon"
        )[:7]
        status_col = gray

    _draw_text(canvas, full_status, _center_x(full_status, 0, LEFT_W), 28, status_col)


def _sorted_leaders(details: dict, stat_key: str) -> list[dict]:
    """All players from both teams sorted by stat_key descending, tagged with 'side'."""
    players: list[dict] = []
    for side in ("away", "home"):
        for p in details.get(side, {}).get("players", []):
            players.append({**p, "side": side})
    players.sort(key=lambda p: p.get(stat_key, 0), reverse=True)
    return players


# Maps panel_view key -> (header label, stat dict key)
_STAT_VIEWS: dict[str, tuple[str, str]] = {
    "pts": ("PTS", "points"),
    "ast": ("AST", "assists"),
    "reb": ("REB", "rebounds"),
    "fouls": ("FOULS", "fouls"),
}


def _render_right_stat(
    canvas,
    details: dict | None,
    game: dict,
    stat_key: str,
    label: str,
) -> None:
    """Right panel — compact stat leader board with possession indicator.

    Layout (x=29..63, 35px wide):
      y=5           stat label header, centered
      y=7           thin separator
      y=14,22,30    top 3 leaders:
                      jersey (x=37, team color)
                      value  (right-aligned to x=62, white)
      x=63          possession column:
                      y=0..4  lit in away color if away has ball
                      y=27..31 lit in home color if home has ball
    """
    away_col = _team_color(game.get("away_color", "ffffff"))
    home_col = _team_color(game.get("home_color", "ffffff"))
    gray = _color(80, 80, 80)
    white = _color(210, 210, 210)

    # Header + separator
    _draw_text(canvas, label, _center_x(label, RIGHT_X, RIGHT_W), 5, white)
    for x in range(RIGHT_X, MATRIX_W - 1):  # leave x=63 for possession
        canvas.SetPixel(x, 7, 55, 55, 55)

    _draw_possession_column(canvas, game)

    if not details:
        _draw_text(canvas, "No Data", _center_x("No Data", RIGHT_X, RIGHT_W), 20, gray)
        return

    leaders = _sorted_leaders(details, stat_key)[:3]

    x_jersey = RIGHT_X + 8  # jersey left-anchored
    x_val_end = MATRIX_W - 1  # value right-aligns so rightmost pixel is at x=62

    for player, text_y in zip(leaders, [14, 22, 30]):
        jersey = str(player.get("jersey", "?"))[:2]
        val = player.get(stat_key, 0)
        side = player.get("side", "away")
        team_col = away_col if side == "away" else home_col
        val_str = str(val)

        _draw_text(canvas, jersey, x_jersey, text_y, team_col)
        _draw_text(canvas, val_str, x_val_end - len(val_str) * _CW, text_y, white)


def render_game(canvas, game: dict, details: dict | None, panel_view: str) -> None:
    """Render a full frame.

    panel_view: one of "pts", "ast", "reb", "fouls"
    details: result of get_nba_game_details(), or None if unavailable
    """
    canvas.Clear()
    _draw_divider(canvas)
    _render_left_panel(canvas, game)

    label, stat_key = _STAT_VIEWS.get(panel_view, ("PTS", "points"))
    _render_right_stat(canvas, details, game, stat_key, label)


# ── Split-screen overview helpers ─────────────────────────────────────────────
#
# Each panel occupies x=0..30 (left) or x=32..63 (right), full 32px height.
# A vertical dim line at x=31 separates the two panels.
#
# Panel layout:
#   y=0..9    Away section  — team color bg, abbr + score, baseline y=7
#             (2px top pad · 6px text · 2px bottom pad = 10px)
#   y=10      Horizontal border
#   y=11..20  Home section  — same treatment, baseline y=18
#   y=21..31  Info strip    — black bg; sport-specific content

_OVR_LEFT_X = 0
_OVR_DIV_X = 31
_OVR_RIGHT_X = 32
_OVR_LEFT_W = 31  # x=0..30
_OVR_RIGHT_W = 32  # x=32..63


def _mini_diamond(
    canvas, x0: int, y0: int, on_first: bool, on_second: bool, on_third: bool
) -> None:
    """Draw a 5×5 baseball diamond with top-left corner at (x0, y0)."""
    _L = (35, 35, 35)
    canvas.SetPixel(x0 + 3, y0 + 1, *_L)
    canvas.SetPixel(x0 + 1, y0 + 1, *_L)
    canvas.SetPixel(x0 + 3, y0 + 3, *_L)
    canvas.SetPixel(x0 + 1, y0 + 3, *_L)

    def _b(bx, by, occ):
        r, g, b = _BASE_OCC if occ else _BASE_EMPTY
        canvas.SetPixel(bx, by, r, g, b)

    _b(x0 + 2, y0, on_second)
    _b(x0 + 4, y0 + 2, on_first)
    _b(x0 + 2, y0 + 4, False)  # home plate
    _b(x0, y0 + 2, on_third)


def _render_nba_overview_panel(canvas, game: dict, x0: int, w: int) -> None:
    """Render one NBA game in a split-screen overview panel."""
    state, x1 = _render_overview_panel_base(canvas, game, x0, w)
    period = game.get("period", 0)
    clock = game.get("clock", "")
    status_detail = game.get("status_detail", "")
    yellow = _color(255, 220, 0)
    gray = _color(140, 140, 140)

    # Info strip y=21..31 — status centered at y=28
    if state == "in":
        p = "OT" if period == 5 else (f"OT{period-4}" if period > 5 else f"Q{period}")
        st = f"{p} {clock}" if clock else p
        while len(st) * _CW > w - 2 and " " in st:
            st = st.rsplit(" ", 1)[0]
        _draw_text(canvas, st, x0 + max(0, (w - len(st) * _CW) // 2), 28, yellow)
    elif state == "post":
        _draw_text(canvas, "Final", x0 + max(0, (w - 5 * _CW) // 2), 28, gray)
    else:
        st = (_format_game_time(game.get("game_date", "")) or status_detail or "Soon")[
            :7
        ]
        _draw_text(canvas, st, x0 + max(0, (w - len(st) * _CW) // 2), 28, gray)


def _render_mlb_overview_panel(canvas, game: dict, x0: int, w: int) -> None:
    """Render one MLB game in a split-screen overview panel."""
    state, x1 = _render_overview_panel_base(canvas, game, x0, w)
    period = game.get("period", 0)
    inning_half = game.get("inning_half")
    status_detail = game.get("status_detail", "")
    yellow = _color(255, 220, 0)
    gray = _color(140, 140, 140)
    white = _color(180, 180, 180)

    # Info strip y=21..31
    if state == "in":
        balls = game.get("balls") or 0
        strikes = game.get("strikes") or 0
        outs = game.get("outs") or 0

        # Row 1 (y=22..26): mini 5×5 diamond + "B-S" count right-aligned
        _mini_diamond(
            canvas,
            x0 + 1,
            22,
            game.get("on_first", False),
            game.get("on_second", False),
            game.get("on_third", False),
        )
        count_str = f"{balls}-{strikes}"
        _draw_text(canvas, count_str, x1 - len(count_str) * _CW + 1, 26, white)

        # Row 2 (y=28..30): outs boxes (3 × 3px) left + inning right
        for i in range(3):
            bx = x0 + 1 + i * 5
            r, g, b = _OUT_COL if i < outs else (40, 40, 40)
            _fill_rect(canvas, bx, 28, bx + 2, 30, r, g, b)

        half = "T" if inning_half == "top" else "B"
        inn = f"{half}{period}" if period else "?"
        _draw_text(canvas, inn, x1 - len(inn) * _CW + 1, 31, yellow)

    elif state == "post":
        _draw_text(canvas, "Final", x0 + max(0, (w - 5 * _CW) // 2), 28, gray)
    else:
        st = (_format_game_time(game.get("game_date", "")) or status_detail or "Soon")[
            :7
        ]
        _draw_text(canvas, st, x0 + max(0, (w - len(st) * _CW) // 2), 28, gray)


def render_game_overview(canvas, game_a: dict, game_b: dict | None) -> None:
    """Split-screen NBA overview: two games side by side."""
    canvas.Clear()
    # Vertical divider
    for y in range(MATRIX_H):
        canvas.SetPixel(_OVR_DIV_X, y, 35, 35, 35)
    _render_nba_overview_panel(canvas, game_a, _OVR_LEFT_X, _OVR_LEFT_W)
    if game_b:
        _render_nba_overview_panel(canvas, game_b, _OVR_RIGHT_X, _OVR_RIGHT_W)


def render_no_games(canvas, sport_label: str) -> None:
    canvas.Clear()
    white = _color(255, 255, 255)
    gray = _color(100, 100, 100)
    _draw_text(canvas, sport_label, _center_x(sport_label, 0, MATRIX_W), 13, white)
    _draw_text(canvas, "No Games", _center_x("No Games", 0, MATRIX_W), 25, gray)


# ── Baseball (MLB) ────────────────────────────────────────────────────────────
#
# Focus layout (64×32):
#   Left panel  (x=0..27):  away / home score rows (y=0..9 / y=10..19)
#                            status zone y=20..31 (LIVE):
#                              inning label centred at baseline y=25
#                              out squares (3×2px) at x=1,5,9 y=27..28
#                              count "B-S" right-aligned baseline y=31
#   Divider     (x=28):     dim vertical line
#   Right panel (x=29..63) LIVE:
#     y=0..13   Pitch-result box (x=29..38) | diamond cx=52 cy=7 r=5
#     y=14      separator
#     y=21      "PITCH" or "BAT" label (alternates every 10 s)
#     y=30      pitcher or batter last name (alternates every 10 s)
#   Right panel POST: W/L decisions / top hitters / top RBI (cycling views)
#
# Overview layout: same as basketball overview but status strip carries
#   a mini 5×5 diamond + inning label + BSO dots.

_BALL_COL = (30, 80, 220)  # blue — ball
_STRIKE_COL = (210, 40, 40)  # red — strike
_OUT_COL = (210, 40, 0)
_BSO_DIM = (28, 28, 28)
_DIAMOND_LINE = (30, 30, 30)
_BASE_EMPTY = (50, 40, 25)
_BASE_OCC = (230, 170, 30)  # golden yellow for occupied base

_PITCH_COL: dict[str, tuple[int, int, int]] = {
    "B": _BALL_COL,
    "S": _STRIKE_COL,
    "F": (180, 100, 30),  # foul: orange
}

# Pitch zone box dimensions (x=29..41, y=0..18 — 13×19px)
_PZ_X0, _PZ_X1 = 29, 41
_PZ_Y0, _PZ_Y1 = 0, 18
# Strike zone outline inside the box (represents the actual strike zone)
_SZ_X0, _SZ_X1 = 31, 39
_SZ_Y0, _SZ_Y1 = 4, 14


def _draw_baseball_diamond(
    canvas,
    cx: int,
    cy: int,
    r: int,
    on_first: bool,
    on_second: bool,
    on_third: bool,
) -> None:
    """Draw a baseball diamond centred at (cx, cy) with half-width r."""
    base_2b = (cx, cy - r)
    base_1b = (cx + r, cy)
    base_hp = (cx, cy + r)
    base_3b = (cx - r, cy)

    for i in range(1, r):
        canvas.SetPixel(base_hp[0] + i, base_hp[1] - i, *_DIAMOND_LINE)  # HP→1B
        canvas.SetPixel(base_1b[0] - i, base_1b[1] - i, *_DIAMOND_LINE)  # 1B→2B
        canvas.SetPixel(base_2b[0] - i, base_2b[1] + i, *_DIAMOND_LINE)  # 2B→3B
        canvas.SetPixel(base_3b[0] + i, base_3b[1] + i, *_DIAMOND_LINE)  # 3B→HP

    def _base(bx, by, occupied):
        rgb = _BASE_OCC if occupied else _BASE_EMPTY
        canvas.SetPixel(bx, by, *rgb)

    _base(*base_2b, on_second)
    _base(*base_1b, on_first)
    _base(*base_hp, False)  # home plate — always unlit
    _base(*base_3b, on_third)


def _draw_bso_dots(canvas, balls, strikes, outs, y: int) -> None:
    """Draw two rows of BSO dots at y and y+1.

    Balls (4, green): x=29,30 | 32,33 | 35,36 | 38,39
    Strikes (3, yellow): x=41,42 | 44,45 | 47,48
    Outs (3, red): x=50,51 | 53,54 | 56,57
    """
    balls = balls or 0
    strikes = strikes or 0
    outs = outs or 0

    for i in range(4):
        r, g, b = _BALL_COL if i < balls else _BSO_DIM
        x = RIGHT_X + i * 3
        canvas.SetPixel(x, y, r, g, b)
        canvas.SetPixel(x, y + 1, r, g, b)

    for i in range(3):
        r, g, b = _STRIKE_COL if i < strikes else _BSO_DIM
        x = RIGHT_X + 12 + i * 3
        canvas.SetPixel(x, y, r, g, b)
        canvas.SetPixel(x, y + 1, r, g, b)

    for i in range(3):
        r, g, b = _OUT_COL if i < outs else _BSO_DIM
        x = RIGHT_X + 21 + i * 3
        canvas.SetPixel(x, y, r, g, b)
        canvas.SetPixel(x, y + 1, r, g, b)


def _render_baseball_left_panel(canvas, game: dict) -> None:
    """Left panel for baseball — team score rows + status zone y=20..31."""
    state = _render_focus_left_header(canvas, game)
    period = game.get("period", 0)
    inning_half = game.get("inning_half")
    status_detail = game.get("status_detail", "")
    outs = game.get("outs") or 0
    balls = game.get("balls") or 0
    strikes = game.get("strikes") or 0
    yellow = _color(255, 220, 0)
    gray = _color(160, 160, 160)
    white = _color(200, 200, 200)

    if state == "in":
        half = "T" if inning_half == "top" else "B"
        inning_label = f"{half}{period}" if period else "Live"
        # Inning centred at baseline y=25
        _draw_text(canvas, inning_label, _center_x(inning_label, 0, LEFT_W), 25, yellow)
        # Out squares — 3 × 2px wide at y=27..28, left-aligned (x=1,5,9)
        for i in range(3):
            r, g, b = _OUT_COL if i < outs else (40, 40, 40)
            _fill_rect(canvas, 1 + i * 4, 27, 2 + i * 4, 28, r, g, b)
        # Count: balls in blue, dash in gray, strikes in red — right-aligned y=31
        # Count is always single digits (max 3-2), so exactly 3 chars = 12px
        cx = LEFT_W - 3 * _CW
        _draw_text(canvas, str(balls), cx, 31, _color(*_BALL_COL))
        _draw_text(canvas, "-", cx + _CW, 31, gray)
        _draw_text(canvas, str(strikes), cx + 2 * _CW, 31, _color(*_STRIKE_COL))
    elif state == "post":
        _draw_text(canvas, "Final", _center_x("Final", 0, LEFT_W), 28, gray)
    else:
        raw = (_format_game_time(game.get("game_date", "")) or status_detail or "Soon")[
            :7
        ]
        _draw_text(canvas, raw, _center_x(raw, 0, LEFT_W), 28, gray)


def _all_batters(details: dict) -> list[dict]:
    players = []
    for side in ("away", "home"):
        for p in details.get(side, {}).get("batters", []):
            players.append({**p, "side": side})
    return players


def _draw_pitch_zone(canvas, pitches: list[dict]) -> None:
    """Draw all pitches of the current at-bat on the 13×19 pitch zone (x=29..41, y=0..18).

    Each pitch is a dict with keys: result ("B"/"S"/"F"), x (float|None), y (float|None).
    Draws a 1px coloured dot per pitch when coordinates are available, or shows the
    last-pitch letter centred when no coordinates have come through yet.
    """
    bx0, bx1, by0, by1 = _PZ_X0, _PZ_X1, _PZ_Y0, _PZ_Y1
    iw = bx1 - bx0 - 1  # interior width  = 11
    ih = by1 - by0 - 1  # interior height = 17

    # Outer border
    dim = (35, 35, 35)
    for x in range(bx0, bx1 + 1):
        canvas.SetPixel(x, by0, *dim)
        canvas.SetPixel(x, by1, *dim)
    for y in range(by0 + 1, by1):
        canvas.SetPixel(bx0, y, *dim)
        canvas.SetPixel(bx1, y, *dim)

    # Strike zone outline
    dim2 = (22, 22, 22)
    for x in range(_SZ_X0, _SZ_X1 + 1):
        canvas.SetPixel(x, _SZ_Y0, *dim2)
        canvas.SetPixel(x, _SZ_Y1, *dim2)
    for y in range(_SZ_Y0 + 1, _SZ_Y1):
        canvas.SetPixel(_SZ_X0, y, *dim2)
        canvas.SetPixel(_SZ_X1, y, *dim2)

    if not pitches:
        return

    has_coords = any(p.get("x") is not None for p in pitches)

    if has_coords:
        for p in pitches:
            col = _PITCH_COL.get(p.get("result", ""), (150, 150, 150))
            px_raw, py_raw = p.get("x"), p.get("y")
            if px_raw is None or py_raw is None:
                continue
            # Normalise: ESPN ~0-250 range, clamp to [0,1]
            nx = max(0.0, min(1.0, (float(px_raw) - 25) / 200))
            ny = max(0.0, min(1.0, (float(py_raw) - 25) / 200))
            dot_x = int(bx0 + 1 + nx * iw)
            dot_y = int(by0 + 1 + ny * ih)
            canvas.SetPixel(dot_x, dot_y, *col)
    else:
        # No coordinates — show last pitch letter centred
        last = pitches[-1]
        result = last.get("result", "")
        if result:
            col = _color(*_PITCH_COL.get(result, (150, 150, 150)))
            lx = bx0 + 1 + (iw - _CW) // 2
            ly = by0 + 1 + (ih + _CH) // 2
            _draw_text(canvas, result, lx, ly, col)


def _render_baseball_right_live(canvas, game: dict, details: dict | None) -> None:
    """Right panel for a live baseball game.

    Layout (x=29..63):
      y=0..18   Pitch zone box (x=29..41) | diamond cx=52 cy=9 r=5 (x=47..57)
      y=19      separator
      y=25      "PITCH" or "BAT" label — alternates every 10 s
      y=31      pitcher or batter last name
    """
    inning_half = game.get("inning_half")
    d = details or {}

    _draw_pitch_zone(canvas, d.get("current_ab_pitches", []))

    # Diamond — centred at x=52, y=9, r=5  (x=47..57, y=4..14)
    _draw_baseball_diamond(
        canvas,
        52,
        9,
        5,
        game.get("on_first", False),
        game.get("on_second", False),
        game.get("on_third", False),
    )

    # Separator
    for x in range(RIGHT_X, MATRIX_W):
        canvas.SetPixel(x, 19, 45, 45, 45)

    # Alternating pitcher / batter last name every 10 s
    show_pitcher = (int(time.time()) // 10) % 2 == 0

    if inning_half == "top":
        batting_col = _team_color(game.get("away_color", "ffffff"))
        pitching_col = _team_color(game.get("home_color", "ffffff"))
    else:
        batting_col = _team_color(game.get("home_color", "ffffff"))
        pitching_col = _team_color(game.get("away_color", "ffffff"))

    gray = _color(100, 100, 100)
    if show_pitcher:
        label = "PITCH"
        name = (game.get("pitcher_name") or "")[:8]
        name_col = pitching_col
    else:
        label = "BAT"
        name = (game.get("batter_name") or "")[:8]
        name_col = batting_col

    # Label directly above name — 6px chars, baseline y=25 then y=31
    _draw_text(canvas, label, _center_x(label, RIGHT_X, RIGHT_W), 25, gray)
    _draw_text(canvas, name, _center_x(name, RIGHT_X, RIGHT_W), 31, name_col)


def _render_baseball_right_post(
    canvas, game: dict, details: dict | None, panel_view: str
) -> None:
    """Right panel for a finished baseball game — cycles decisions / hits / rbi."""
    white = _color(210, 210, 210)
    green = _color(0, 200, 80)
    red = _color(220, 50, 50)
    gray = _color(80, 80, 80)

    label_map = {"decisions": "PITCH", "hits": "HITS", "rbi": "RBI"}
    label = label_map.get(panel_view, "")
    _draw_text(canvas, label, _center_x(label, RIGHT_X, RIGHT_W), 5, white)
    for x in range(RIGHT_X, MATRIX_W):
        canvas.SetPixel(x, 7, 40, 40, 40)

    if not details:
        _draw_text(canvas, "No Data", _center_x("No Data", RIGHT_X, RIGHT_W), 20, gray)
        return

    if panel_view == "decisions":
        # Show top pitcher from each team (most innings pitched)
        away_col = _team_color(game.get("away_color", "ffffff"))
        home_col = _team_color(game.get("home_color", "ffffff"))

        for side, col, y in [("away", away_col, 16), ("home", home_col, 26)]:
            pitchers = details.get(side, {}).get("pitchers", [])
            if pitchers:
                # Sort by IP descending (starter is usually first and longest)
                top = max(pitchers, key=lambda p: float(p.get("ip", "0") or "0"))
                name = (top.get("name", "") or "?").split()[-1][:5]
                ip = (top.get("ip") or "")[:4]
                _draw_text(canvas, name, RIGHT_X + 1, y, col)
                if ip:
                    _draw_text(canvas, ip, MATRIX_W - 1 - len(ip) * _CW, y, white)

    elif panel_view in ("hits", "rbi"):
        stat_key = "hits" if panel_view == "hits" else "rbi"
        batters = sorted(
            _all_batters(details), key=lambda p: p.get(stat_key, 0), reverse=True
        )
        away_col = _team_color(game.get("away_color", "ffffff"))
        home_col = _team_color(game.get("home_color", "ffffff"))

        for player, text_y in zip(batters[:3], [14, 21, 28]):
            name = (player.get("name", "") or "?").split()[-1][:5]
            val = player.get(stat_key, 0)
            side = player.get("side", "away")
            team_col = away_col if side == "away" else home_col
            val_str = str(val)
            _draw_text(canvas, name, RIGHT_X + 1, text_y, team_col)
            _draw_text(
                canvas, val_str, MATRIX_W - 1 - len(val_str) * _CW, text_y, white
            )


def render_baseball_game(
    canvas, game: dict, details: dict | None, panel_view: str
) -> None:
    """Render a full baseball focus frame.

    panel_view: "live" | "decisions" | "hits" | "rbi"
    """
    canvas.Clear()
    _draw_divider(canvas)
    _render_baseball_left_panel(canvas, game)

    state = game.get("state", "pre")
    if state == "in":
        _render_baseball_right_live(canvas, game, details)
    else:
        _render_baseball_right_post(canvas, game, details, panel_view)


def render_baseball_overview(canvas, game_a: dict, game_b: dict | None) -> None:
    """Split-screen baseball overview: two games side by side."""
    canvas.Clear()
    for y in range(MATRIX_H):
        canvas.SetPixel(_OVR_DIV_X, y, 35, 35, 35)
    _render_mlb_overview_panel(canvas, game_a, _OVR_LEFT_X, _OVR_LEFT_W)
    if game_b:
        _render_mlb_overview_panel(canvas, game_b, _OVR_RIGHT_X, _OVR_RIGHT_W)


# ── Hockey (NHL) ───────────────────────────────────────────────────────────────
#
# Focus layout (64×32):
#   Left panel (x=0..27):  away / home score rows; status zone y=20..31
#                           period label + clock (e.g. "P2 14:23")
#   Divider (x=28):         dim vertical line
#   Right panel (x=29..63) cycles 4 views every PANEL_CYCLE seconds:
#     "stats"    — SOG / HIT / BLK comparison (away left · label centre · home right)
#     "goals"    — goal scorers in order (jersey + period)
#     "away_ice" — jerseys of away team players on ice, 3×2 grid
#     "home_ice" — jerseys of home team players on ice, 3×2 grid
#
# Overview layout: same structure as NBA overview (period + clock in info strip).


def _nhl_period_label(period: int) -> str:
    if period <= 3:
        return f"P{period}"
    if period == 4:
        return "OT"
    return "SO"


def _render_hockey_left_panel(canvas, game: dict, details: dict | None = None) -> None:
    state = _render_focus_left_header(canvas, game)
    period = game.get("period", 0)
    clock = game.get("clock", "")
    status_detail = game.get("status_detail", "")
    yellow = _color(255, 220, 0)
    gray = _color(160, 160, 160)

    if state == "in":
        p_label = _nhl_period_label(period)
        full_status = f"{p_label} {clock}" if clock else p_label
        while len(full_status) * _CW > LEFT_W and " " in full_status:
            full_status = full_status.rsplit(" ", 1)[0]
        _draw_text(canvas, full_status, _center_x(full_status, 0, LEFT_W), 28, yellow)

        # Power play indicator — show "PP" in the PP team's color at y=22
        d = details or {}
        if d.get("away", {}).get("on_power_play"):
            pp_col = _team_color(game.get("away_alt_color", "ffffff"))
            _draw_text(canvas, "PP", _center_x("PP", 0, LEFT_W), 22, pp_col)
        elif d.get("home", {}).get("on_power_play"):
            pp_col = _team_color(game.get("home_alt_color", "ffffff"))
            _draw_text(canvas, "PP", _center_x("PP", 0, LEFT_W), 22, pp_col)
    elif state == "post":
        _draw_text(canvas, "Final", _center_x("Final", 0, LEFT_W), 28, gray)
    else:
        st = (_format_game_time(game.get("game_date", "")) or status_detail or "Soon")[
            :7
        ]
        _draw_text(canvas, st, _center_x(st, 0, LEFT_W), 28, gray)


def _render_hockey_right_stats(canvas, game: dict, details: dict | None) -> None:
    """Right panel — shots / hits / blocks comparison.

    Layout per row (y=12, 20, 28):
      away value  left-aligned  x=30
      label       centred       in right panel
      home value  right-aligned x=63
    """
    away_col = _team_color(game.get("away_color", "ffffff"))
    home_col = _team_color(game.get("home_color", "ffffff"))
    gray = _color(100, 100, 100)

    d = details or {}
    away_s = d.get("away", {}).get("stats", {})
    home_s = d.get("home", {}).get("stats", {})

    for label, key, y in [
        ("SOG", "shots", 12),
        ("HIT", "hits", 20),
        ("BLK", "blocks", 28),
    ]:
        aval = str(away_s.get(key, 0))
        hval = str(home_s.get(key, 0))
        _draw_text(canvas, aval, RIGHT_X + 1, y, away_col)
        _draw_text(canvas, label, _center_x(label, RIGHT_X, RIGHT_W), y, gray)
        _draw_text(canvas, hval, MATRIX_W - len(hval) * _CW, y, home_col)


def _render_hockey_right_goals(canvas, game: dict, details: dict | None) -> None:
    """Right panel — goal scorers, most recent first, 4 per page.

    Paginates every 15 s when there are more than 4 goals.
    """
    away_col = _team_color(game.get("away_color", "ffffff"))
    home_col = _team_color(game.get("home_color", "ffffff"))
    white = _color(210, 210, 210)
    gray = _color(100, 100, 100)

    # Reverse so most recent goal is first
    goals = list(reversed((details or {}).get("goals", [])))

    _draw_text(canvas, "GOAL", _center_x("GOAL", RIGHT_X, RIGHT_W), 5, white)
    for x in range(RIGHT_X, MATRIX_W):
        canvas.SetPixel(x, 7, 40, 40, 40)

    if not goals:
        _draw_text(
            canvas, "No Goals", _center_x("No Goals", RIGHT_X, RIGHT_W), 20, gray
        )
        return

    if len(goals) > 4:
        page = (int(time.time()) // 15) % 2
        page_goals = goals[page * 4 : page * 4 + 4]
    else:
        page_goals = goals[:4]

    for goal, y in zip(page_goals, [13, 19, 25, 31]):
        jersey = str(goal.get("jersey", "?"))[:2]
        period = goal.get("period", 0)
        side = goal.get("side", "away")
        p_label = _nhl_period_label(period) if period else "?"
        col = away_col if side == "away" else home_col

        _draw_text(canvas, jersey, RIGHT_X + 1, y, col)
        _draw_text(canvas, p_label, MATRIX_W - len(p_label) * _CW, y, gray)


def _render_hockey_right_on_ice(
    canvas, game: dict, details: dict | None, side: str
) -> None:
    """Right panel — jersey numbers of players on ice (3×2 grid)."""
    team_col = _team_color(game.get(f"{side}_color", "ffffff"))
    white = _color(200, 200, 200)
    gray = _color(80, 80, 80)

    d = details or {}
    abbr = d.get(side, {}).get("abbreviation", side.upper()[:4])
    jerseys = d.get(side, {}).get("on_ice", [])

    _draw_text(canvas, abbr, _center_x(abbr, RIGHT_X, RIGHT_W), 6, white)
    for x in range(RIGHT_X, MATRIX_W):
        canvas.SetPixel(x, 8, 40, 40, 40)

    if not jerseys:
        _draw_text(canvas, "No Data", _center_x("No Data", RIGHT_X, RIGHT_W), 20, gray)
        return

    # 3 columns at x=30, 42, 54 · 2 rows at y=17, 27
    col_x = [RIGHT_X + 1, RIGHT_X + 13, RIGHT_X + 25]
    for row_idx, y in enumerate([17, 27]):
        for col_idx, x in enumerate(col_x):
            i = row_idx * 3 + col_idx
            if i < len(jerseys):
                _draw_text(canvas, str(jerseys[i])[:2], x, y, team_col)


def render_hockey_game(
    canvas, game: dict, details: dict | None, panel_view: str
) -> None:
    """Render a full hockey focus frame."""
    canvas.Clear()
    _draw_divider(canvas)
    _render_hockey_left_panel(canvas, game, details)
    if panel_view == "goals":
        _render_hockey_right_goals(canvas, game, details)
    elif panel_view == "away_ice":
        _render_hockey_right_on_ice(canvas, game, details, "away")
    elif panel_view == "home_ice":
        _render_hockey_right_on_ice(canvas, game, details, "home")
    else:  # "stats" or fallback
        _render_hockey_right_stats(canvas, game, details)


def _render_hockey_overview_panel(canvas, game: dict, x0: int, w: int) -> None:
    state, x1 = _render_overview_panel_base(canvas, game, x0, w)
    period = game.get("period", 0)
    clock = game.get("clock", "")
    status_detail = game.get("status_detail", "")
    yellow = _color(255, 220, 0)
    gray = _color(140, 140, 140)

    if state == "in":
        p = _nhl_period_label(period)
        st = f"{p} {clock}" if clock else p
        while len(st) * _CW > w - 2 and " " in st:
            st = st.rsplit(" ", 1)[0]
        _draw_text(canvas, st, x0 + max(0, (w - len(st) * _CW) // 2), 28, yellow)
    elif state == "post":
        _draw_text(canvas, "Final", x0 + max(0, (w - 5 * _CW) // 2), 28, gray)
    else:
        st = (_format_game_time(game.get("game_date", "")) or status_detail or "Soon")[
            :7
        ]
        _draw_text(canvas, st, x0 + max(0, (w - len(st) * _CW) // 2), 28, gray)


def render_hockey_overview(canvas, game_a: dict, game_b: dict | None) -> None:
    """Split-screen NHL overview: two games side by side."""
    canvas.Clear()
    for y in range(MATRIX_H):
        canvas.SetPixel(_OVR_DIV_X, y, 35, 35, 35)
    _render_hockey_overview_panel(canvas, game_a, _OVR_LEFT_X, _OVR_LEFT_W)
    if game_b:
        _render_hockey_overview_panel(canvas, game_b, _OVR_RIGHT_X, _OVR_RIGHT_W)


# ── Soccer ─────────────────────────────────────────────────────────────────────
#
# Focus layout (64×32):
#   Left panel (x=0..27):  away / home score rows; status zone y=20..31
#                           match time / "Final" / kickoff time
#   Divider (x=28):         dim vertical line
#   Right panel (x=29..63) cycles between:
#     "stats" — possession / shots / SOG comparison
#     "goals" — goal scorers with minute
#
# Overview layout: same structure as other sports.


def _soccer_period_label(period: int, clock: str, state: str) -> str:
    """Return a compact match time string for the left panel."""
    if state == "post":
        return "Final"
    if state == "pre":
        return ""
    if period == 1:
        return f"1H {clock}" if clock else "1H"
    if period == 2:
        return f"2H {clock}" if clock else "2H"
    if period >= 3:
        return f"ET {clock}" if clock else "ET"
    return clock or ""


def _render_soccer_left_panel(canvas, game: dict) -> None:
    state = _render_focus_left_header(canvas, game)
    period = game.get("period", 0)
    clock = game.get("clock", "")
    status_detail = game.get("status_detail", "")
    yellow = _color(255, 220, 0)
    gray = _color(160, 160, 160)

    if state == "in":
        label = _soccer_period_label(period, clock, state)
        while len(label) * _CW > LEFT_W and " " in label:
            label = label.rsplit(" ", 1)[0]
        _draw_text(canvas, label, _center_x(label, 0, LEFT_W), 28, yellow)
    elif state == "post":
        _draw_text(canvas, "Final", _center_x("Final", 0, LEFT_W), 28, gray)
    else:
        st = (_format_game_time(game.get("game_date", "")) or status_detail or "Soon")[
            :7
        ]
        _draw_text(canvas, st, _center_x(st, 0, LEFT_W), 28, gray)


def _render_soccer_right_stats(canvas, game: dict, details: dict | None) -> None:
    """Right panel — yellow cards / red cards / shots comparison."""
    away_col = _team_color(game.get("away_color", "ffffff"))
    home_col = _team_color(game.get("home_color", "ffffff"))
    yellow = _color(255, 220, 0)
    red = _color(220, 40, 0)
    gray = _color(100, 100, 100)
    white = _color(210, 210, 210)

    _draw_text(canvas, "Stats", _center_x("Stats", RIGHT_X, RIGHT_W), 5, white)
    for x in range(RIGHT_X, MATRIX_W):
        canvas.SetPixel(x, 7, 40, 40, 40)

    d = details or {}
    away_s = d.get("away", {}).get("stats", {})
    home_s = d.get("home", {}).get("stats", {})

    rows = [
        ("YC", "yellows", yellow),
        ("RC", "reds", red),
        ("SHT", "shots", gray),
    ]

    for label, key, label_col, y in [
        (r[0], r[1], r[2], 14 + i * 8) for i, r in enumerate(rows)
    ]:
        aval = str(away_s.get(key, "0"))[:4]
        hval = str(home_s.get(key, "0"))[:4]
        _draw_text(canvas, aval, RIGHT_X + 1, y, away_col)
        _draw_text(canvas, label, _center_x(label, RIGHT_X, RIGHT_W), y, label_col)
        _draw_text(canvas, hval, MATRIX_W - len(hval) * _CW, y, home_col)


def _render_soccer_right_goals(canvas, game: dict, details: dict | None) -> None:
    """Right panel — goal scorers with minute."""
    away_col = _team_color(game.get("away_color", "ffffff"))
    home_col = _team_color(game.get("home_color", "ffffff"))
    white = _color(210, 210, 210)
    gray = _color(100, 100, 100)

    _draw_text(canvas, "Goals", _center_x("Goals", RIGHT_X, RIGHT_W), 5, white)
    for x in range(RIGHT_X, MATRIX_W):
        canvas.SetPixel(x, 7, 40, 40, 40)

    goals = (details or {}).get("goals", [])

    if not goals:
        _draw_text(
            canvas, "No Goals", _center_x("No Goals", RIGHT_X, RIGHT_W), 16, gray
        )
        return

    # Show up to 4 goals, paginate if more
    if len(goals) > 4:
        page = (int(time.time()) // 15) % ((len(goals) - 1) // 4 + 1)
        page_goals = goals[page * 4 : page * 4 + 4]
    else:
        page_goals = goals[:4]

    for goal, y in zip(page_goals, [13, 19, 25, 31]):
        scorer = goal.get("scorer", "?")[:6]
        # Just the minute number, 2 digits max (e.g. "21" not "21'")
        t = goal.get("time", "").replace("'", "").strip()[:2]
        side = goal.get("side", "away")
        col = away_col if side == "away" else home_col
        _draw_text(canvas, scorer, RIGHT_X + 1, y, col)
        _draw_text(canvas, t, MATRIX_W - len(t) * _CW, y, gray)


def render_soccer_game(
    canvas, game: dict, details: dict | None, panel_view: str
) -> None:
    """Render a full soccer focus frame."""
    canvas.Clear()
    _draw_divider(canvas)
    _render_soccer_left_panel(canvas, game)
    if panel_view == "goals":
        _render_soccer_right_goals(canvas, game, details)
    else:  # "stats" or fallback
        _render_soccer_right_stats(canvas, game, details)


def _render_soccer_overview_panel(canvas, game: dict, x0: int, w: int) -> None:
    state, x1 = _render_overview_panel_base(canvas, game, x0, w)
    period = game.get("period", 0)
    clock = game.get("clock", "")
    status_detail = game.get("status_detail", "")
    yellow = _color(255, 220, 0)
    gray = _color(140, 140, 140)

    if state == "in":
        label = _soccer_period_label(period, clock, state)
        while len(label) * _CW > w - 2 and " " in label:
            label = label.rsplit(" ", 1)[0]
        _draw_text(canvas, label, x0 + max(0, (w - len(label) * _CW) // 2), 28, yellow)
    elif state == "post":
        _draw_text(canvas, "Final", x0 + max(0, (w - 5 * _CW) // 2), 28, gray)
    else:
        st = (_format_game_time(game.get("game_date", "")) or status_detail or "Soon")[
            :7
        ]
        _draw_text(canvas, st, x0 + max(0, (w - len(st) * _CW) // 2), 28, gray)


def render_soccer_overview(canvas, game_a: dict, game_b: dict | None) -> None:
    """Split-screen soccer overview: two games side by side."""
    canvas.Clear()
    for y in range(MATRIX_H):
        canvas.SetPixel(_OVR_DIV_X, y, 35, 35, 35)
    _render_soccer_overview_panel(canvas, game_a, _OVR_LEFT_X, _OVR_LEFT_W)
    if game_b:
        _render_soccer_overview_panel(canvas, game_b, _OVR_RIGHT_X, _OVR_RIGHT_W)


# ── Football (NFL / NCAAF) ─────────────────────────────────────────────────────
#
# League-agnostic: every football league (NFL, NCAA, …) renders through these
# functions — the data contract is identical, only the league slug differs.
#
# Focus layout (64×32):
#   Left panel (x=0..27):  away / home score rows — a small football is drawn
#                            beside the abbreviation of the team with the ball;
#                            status zone y=20..31
#                            LIVE:  quarter label (left) + clock (right) @ y=25
#                                   situation centred @ y=31, alternating every
#                                   5s between down & distance ("1st&13") and
#                                   the ball spot ("DEN 25") — drawn in the
#                                   possessing team's color, red in the red zone
#                            POST:  "Final" / "Fin OT"
#                            PRE:   kickoff time
#   Divider (x=28):         dim vertical line
#   Right panel (x=29..63) cycles every PANEL_CYCLE seconds:
#     "stats"   — YD / PS / RS / TO comparison (away left · label centre ·
#                 home right)
#     "scoring" — scoring plays, most recent first (team · TD/FG · quarter)
#     "pass"    — passing leaders, away above home (name + yards/TD)
#     "rush"    — rushing leaders
#     "recv"    — receiving leaders
#
# Overview layout: possession football in the team rows (red in the red zone),
#   info strip carries quarter + clock on one row (y=28). The 11px strip cannot
#   fit a second text row without clipping descenders, so down & distance and
#   the ball spot stay in focus mode.

# Right-panel column anchors (panel spans x=29..63, 35px). Football uses the
# full width — there is no possession column here, the football icon in the
# team row carries possession.
_FB_COL_L = RIGHT_X  # left column: away value / team abbreviation
_FB_COL_M = RIGHT_X + 15  # middle column: scoring play type
_FB_RIGHT_EDGE = MATRIX_W  # right-aligned text ends at x=63

# Right-panel team comparison rows — 2-char labels keep 3-digit values legible.
_FOOTBALL_STAT_ROWS: tuple[tuple[str, str], ...] = (
    ("YD", "yards"),
    ("PS", "pass_yards"),
    ("RS", "rush_yards"),
    ("TO", "turnovers"),
)

# panel_view → (header, details leaders key)
_FOOTBALL_LEADER_VIEWS: dict[str, tuple[str, str]] = {
    "pass": ("PASS", "passing"),
    "rush": ("RUSH", "rushing"),
    "recv": ("RECV", "receiving"),
}

_RED_ZONE_RGB = (255, 40, 0)

# Possession football — 5×3 filled ellipse drawn beside the team abbreviation.
# Leather brown, bright enough to read against a team-color background (which
# is normalized to _BG_PEAK); turns _RED_ZONE_RGB inside the red zone.
_FB_ICON_W = 5
_FB_ICON_H = 3
_FB_ICON_RGB = (205, 120, 45)

# Team-row bounds (y_top, y_bottom) for each layout, used to centre the icon.
_FB_FOCUS_ROWS = {"away": (0, 9), "home": (10, 19)}
_FB_OVERVIEW_ROWS = {"away": (0, 9), "home": (11, 20)}


def _draw_football_icon(canvas, x0: int, y0: int, rgb=_FB_ICON_RGB) -> None:
    """Draw a 5×3 filled football with its top-left corner at (x0, y0).

    .###.
    #####
    .###.
    """
    r, g, b = rgb
    for x in range(x0 + 1, x0 + _FB_ICON_W - 1):
        canvas.SetPixel(x, y0, r, g, b)
        canvas.SetPixel(x, y0 + 2, r, g, b)
    for x in range(x0, x0 + _FB_ICON_W):
        canvas.SetPixel(x, y0 + 1, r, g, b)


def _draw_football_possession(
    canvas, game: dict, x0: int, x1: int, rows: dict, abbr_max: int
) -> None:
    """Mark the team with the ball: a football right of its abbreviation.

    Skipped when the row is too tight to fit the icon between the abbreviation
    and the score (only happens with 4-char abbreviations, i.e. some college
    teams) — the down & distance color still carries possession in that case.
    """
    side = game.get("possession")
    if side not in ("home", "away") or game.get("state") != "in":
        return

    abbr = str(game.get(f"{side}_team", ""))[:abbr_max]
    score = str(game.get(f"{side}_score", 0))
    icon_x = x0 + 1 + len(abbr) * _CW + 1  # 1px gap after the abbreviation
    icon_limit = x1 - len(score) * _CW  # stay clear of the right-aligned score
    if icon_x + _FB_ICON_W - 1 > icon_limit:
        return

    top, bottom = rows[side]
    icon_y = top + (bottom - top + 1 - _FB_ICON_H) // 2
    # Red in the red zone — the only situation cue the overview has room for
    rgb = _RED_ZONE_RGB if game.get("is_red_zone") else _FB_ICON_RGB
    _draw_football_icon(canvas, icon_x, icon_y, rgb)


def _football_period_label(period: int) -> str:
    """Q1–Q4, then OT / OT2 / OT3 …"""
    if period <= 1:
        return "Q1"
    if period <= 4:
        return f"Q{period}"
    if period == 5:
        return "OT"
    return f"OT{period - 4}"


def _football_period_compact(period: int) -> str:
    """2-char period label ('O2' for OT2) so it always fits beside a clock."""
    label = _football_period_label(period)
    return label if len(label) <= 2 else label.replace("OT", "O", 1)


_FB_ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}
_FB_SITUATION_CYCLE = 5  # seconds per situation view


def _football_down_distance(game: dict) -> str:
    """Down & distance, e.g. '1st&13' or '1st&G'. Empty between plays.

    No spaces around the '&': the status row is 28px, and the 4x6 font is fixed
    width, so '1st & 13' (8 chars = 32px) would not fit — '1st&13' (24px) does.
    """
    down = game.get("down") or 0
    if not down:
        return ""
    label = _FB_ORDINALS.get(down, str(down))
    distance = game.get("distance") or 0
    return f"{label}&{distance}" if distance else f"{label}&G"


def _football_ball_spot(game: dict) -> str:
    """Where the ball is, e.g. 'DEN 25' (ESPN's possessionText)."""
    return (game.get("yard_line_text") or "").strip()


def _football_situation_text(game: dict, max_chars: int) -> str:
    """Down & distance and ball spot, alternating every _FB_SITUATION_CYCLE s.

    '1st&13 DEN 25' is 13 chars and never fits a 7-char row, so the two take
    turns. If only one is available it stays put instead of blinking.
    """
    down_distance = _football_down_distance(game)
    spot = _football_ball_spot(game)
    if down_distance and spot:
        show_spot = (int(time.time()) // _FB_SITUATION_CYCLE) % 2 == 1
        text = spot if show_spot else down_distance
    else:
        text = down_distance or spot
    return text[:max_chars]


_FB_MIN_TEXT_PEAK = 100  # below this a primary color is unreadable on black


def _football_team_text_color(game: dict, side: str):
    """Team text color for the black right panel.

    Some primaries are too dark to read on black even after the
    _MIN_BRIGHTNESS boost (Bears navy 0b1c3a, Steelers black 000000), so fall
    back to the alternate color when it is brighter. Teams with a usable
    primary keep it, so a light-gray alternate never replaces a team's real
    color.
    """
    primary = game.get(f"{side}_color") or "ffffff"
    alt = game.get(f"{side}_alt_color") or ""
    try:
        primary_peak = max(_parse_hex(primary))
    except Exception:
        return _team_color(primary)
    if primary_peak >= _FB_MIN_TEXT_PEAK or not alt:
        return _team_color(primary)
    try:
        if max(_parse_hex(alt)) > primary_peak:
            return _team_color(alt)
    except Exception:
        pass
    return _team_color(primary)


def _football_situation_color(game: dict):
    """Color for the down & distance text: red zone red, else possession color."""
    if game.get("is_red_zone"):
        return _color(*_RED_ZONE_RGB)
    possession = game.get("possession")
    if possession in ("home", "away"):
        return _football_team_text_color(game, possession)
    return _color(160, 160, 160)


def _is_halftime(game: dict) -> bool:
    return "half" in (game.get("status_detail") or "").lower()


def _render_football_left_panel(canvas, game: dict) -> None:
    state = _render_focus_left_header(canvas, game)
    _draw_football_possession(canvas, game, 0, LEFT_W - 1, _FB_FOCUS_ROWS, 4)
    period = game.get("period", 0)
    clock = game.get("clock", "")
    yellow = _color(255, 220, 0)
    gray = _color(160, 160, 160)

    if state == "in":
        if _is_halftime(game):
            _draw_text(canvas, "HALF", _center_x("HALF", 0, LEFT_W), 25, yellow)
        elif clock:
            # Quarter left, clock right. A 2-digit-minute clock ("15:00") plus
            # the label fills all 28px, leaving no word gap, so the two are
            # separated by color instead: quarter dim white, clock live yellow.
            label = _football_period_compact(period)
            _draw_text(canvas, label, 0, 25, _color(190, 190, 190))
            _draw_text(canvas, clock, LEFT_W - len(clock) * _CW, 25, yellow)
        else:
            label = _football_period_label(period)
            _draw_text(canvas, label, _center_x(label, 0, LEFT_W), 25, yellow)

        situation = _football_situation_text(game, LEFT_W // _CW)
        if situation:
            _draw_text(
                canvas,
                situation,
                _center_x(situation, 0, LEFT_W),
                31,
                _football_situation_color(game),
            )
    elif state == "post":
        label = "Final" if period <= 4 else "Fin OT"
        _draw_text(canvas, label, _center_x(label, 0, LEFT_W), 28, gray)
    else:
        st = (
            _format_game_time(game.get("game_date", ""))
            or game.get("status_detail", "")
            or "Soon"
        )[:7]
        _draw_text(canvas, st, _center_x(st, 0, LEFT_W), 28, gray)


def _render_football_right_stats(canvas, game: dict, details: dict | None) -> None:
    """Right panel — team comparison rows at y=9/16/23/30."""
    away_col = _football_team_text_color(game, "away")
    home_col = _football_team_text_color(game, "home")
    gray = _color(100, 100, 100)

    d = details or {}
    away_s = d.get("away", {}).get("stats", {})
    home_s = d.get("home", {}).get("stats", {})
    if not away_s and not home_s:
        _draw_text(canvas, "No Data", _center_x("No Data", RIGHT_X, RIGHT_W), 20, gray)
        return

    # away value | label | home value — anchored to the panel edges so 3-digit
    # yardage keeps a gap either side of the label.
    for (label, key), y in zip(_FOOTBALL_STAT_ROWS, [9, 16, 23, 30]):
        aval = str(away_s.get(key, "0"))[:3]
        hval = str(home_s.get(key, "0"))[:3]
        _draw_text(canvas, aval, _FB_COL_L, y, away_col)
        _draw_text(canvas, label, _center_x(label, RIGHT_X, RIGHT_W), y, gray)
        _draw_text(canvas, hval, _FB_RIGHT_EDGE - len(hval) * _CW, y, home_col)


def _render_football_right_scoring(canvas, game: dict, details: dict | None) -> None:
    """Right panel — scoring plays, most recent first, 4 per page."""
    away_col = _football_team_text_color(game, "away")
    home_col = _football_team_text_color(game, "home")
    white = _color(210, 210, 210)
    gray = _color(100, 100, 100)

    _draw_text(canvas, "SCORE", _center_x("SCORE", RIGHT_X, RIGHT_W), 5, white)
    for x in range(RIGHT_X, MATRIX_W):
        canvas.SetPixel(x, 7, 40, 40, 40)

    plays = list(reversed((details or {}).get("scoring", [])))
    if not plays:
        _draw_text(
            canvas, "No Score", _center_x("No Score", RIGHT_X, RIGHT_W), 20, gray
        )
        return

    pages = (len(plays) - 1) // 4 + 1
    page = (int(time.time()) // 15) % pages if pages > 1 else 0
    page_plays = plays[page * 4 : page * 4 + 4]

    # team | play type | quarter — fixed columns so nothing runs together
    # ("DET TD Q1"). The compact period label keeps the last column at 2 chars.
    for play, y in zip(page_plays, [13, 19, 25, 31]):
        abbr = str(play.get("team", ""))[:3]
        kind = str(play.get("type", ""))[:2]
        period = play.get("period", 0)
        p_label = _football_period_compact(period) if period else "?"
        col = away_col if play.get("side") == "away" else home_col

        _draw_text(canvas, abbr, _FB_COL_L, y, col)
        _draw_text(canvas, kind, _FB_COL_M, y, white)
        _draw_text(canvas, p_label, _FB_RIGHT_EDGE - len(p_label) * _CW, y, gray)


def _football_leader_value(leader: dict) -> str:
    """Compact leader line, e.g. '128 2TD' or '56yd'."""
    yards = leader.get("yards", 0)
    tds = leader.get("touchdowns", 0)
    return f"{yards} {tds}TD" if tds else f"{yards}yd"


_FB_NAME_MAX = 8  # 8 chars × 4px = 32px, fits the 35px right panel


def _fit_name(name: str, max_chars: int = _FB_NAME_MAX) -> str:
    """Trim a surname to fit, dropping leading parts before truncating.

    'St. Brown' → 'Brown' (not 'St. Brow'); 'Higginbotham' → 'Higginbo'.
    """
    name = (name or "").strip()
    while len(name) > max_chars and " " in name:
        name = name.split(" ", 1)[1]
    return name[:max_chars]


def _render_football_right_leader(
    canvas, game: dict, details: dict | None, header: str, key: str
) -> None:
    """Right panel — one stat leader per team: name above, yards/TD below."""
    white = _color(210, 210, 210)
    gray = _color(100, 100, 100)

    _draw_text(canvas, header, _center_x(header, RIGHT_X, RIGHT_W), 5, white)
    for x in range(RIGHT_X, MATRIX_W):
        canvas.SetPixel(x, 7, 40, 40, 40)

    d = details or {}
    if not d:
        _draw_text(canvas, "No Data", _center_x("No Data", RIGHT_X, RIGHT_W), 20, gray)
        return

    for side, name_y, val_y in (("away", 13, 19), ("home", 25, 31)):
        leader = d.get(side, {}).get("leaders", {}).get(key) or {}
        col = _football_team_text_color(game, side)
        name = _fit_name(leader.get("name") or game.get(f"{side}_team", ""))
        _draw_text(canvas, name, RIGHT_X + 1, name_y, col)
        value = _football_leader_value(leader) if leader else "-"
        _draw_text(canvas, value, RIGHT_X + 1, val_y, white if leader else gray)


def render_football_game(
    canvas, game: dict, details: dict | None, panel_view: str
) -> None:
    """Render a full football focus frame (NFL, NCAAF, …)."""
    canvas.Clear()
    _draw_divider(canvas)
    _render_football_left_panel(canvas, game)

    if panel_view == "scoring":
        _render_football_right_scoring(canvas, game, details)
    elif panel_view in _FOOTBALL_LEADER_VIEWS:
        header, key = _FOOTBALL_LEADER_VIEWS[panel_view]
        _render_football_right_leader(canvas, game, details, header, key)
    else:  # "stats" or fallback
        _render_football_right_stats(canvas, game, details)


def _render_football_overview_panel(canvas, game: dict, x0: int, w: int) -> None:
    state, x1 = _render_overview_panel_base(canvas, game, x0, w)
    _draw_football_possession(canvas, game, x0, x1, _FB_OVERVIEW_ROWS, 3)
    period = game.get("period", 0)
    clock = game.get("clock", "")
    yellow = _color(255, 220, 0)
    gray = _color(140, 140, 140)

    if state == "in":
        # Single row at y=28, like the other sports' overviews. The strip is
        # only 11px (y=21..31) so a second text row would overlap: 'Q' has a
        # descender, and the row below would clip its tail into an 'O'.
        # Possession lives in the football icon, situation detail in focus mode.
        if _is_halftime(game):
            _draw_text(canvas, "HALF", x0 + max(0, (w - 4 * _CW) // 2), 28, yellow)
        else:
            label = _football_period_compact(period)
            _draw_text(canvas, label, x0 + 1, 28, yellow)
            # +1 for the left inset — keep the clock clear of the label
            if clock and (len(label) + len(clock)) * _CW + 1 <= w:
                _draw_text(canvas, clock, x1 - len(clock) * _CW + 1, 28, yellow)
    elif state == "post":
        _draw_text(canvas, "Final", x0 + max(0, (w - 5 * _CW) // 2), 28, gray)
    else:
        st = (
            _format_game_time(game.get("game_date", ""))
            or game.get("status_detail", "")
            or "Soon"
        )[:7]
        _draw_text(canvas, st, x0 + max(0, (w - len(st) * _CW) // 2), 28, gray)


def render_football_overview(canvas, game_a: dict, game_b: dict | None) -> None:
    """Split-screen football overview: two games side by side."""
    canvas.Clear()
    for y in range(MATRIX_H):
        canvas.SetPixel(_OVR_DIV_X, y, 35, 35, 35)
    _render_football_overview_panel(canvas, game_a, _OVR_LEFT_X, _OVR_LEFT_W)
    if game_b:
        _render_football_overview_panel(canvas, game_b, _OVR_RIGHT_X, _OVR_RIGHT_W)
