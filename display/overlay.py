"""Shared full-screen display overlay.

A single entry point, ``render_overlay(canvas, overlay)``, that any display mode
calls at the top of its render loop. When the API has set a ``settings["overlay"]``
(surfaced to each mode's settings poll), this blanks the matrix and draws the
message over everything, short-circuiting normal rendering.

Overlay dicts (written by the API button handler / display-overlay endpoint):
    {"kind": "reset_prompt", "seconds_left": N}  -> "FACTORY RESET" + "Hold Ns"
    {"kind": "reset_running"}                    -> "FACTORY" + "RESET"

Returns True when it rendered an overlay (caller should swap + skip its own
rendering), False when there is no overlay (caller renders normally).

Font/graphics handling mirrors the sports renderer: use rgbmatrix.graphics on
hardware, fall back to PIL for the headless mock so overlays show in dev too.
"""

from pathlib import Path

try:
    from matrix import USING_HARDWARE
except Exception:  # pragma: no cover - matrix always importable in a display
    USING_HARDWARE = False

MATRIX_W = 64
MATRIX_H = 32

_FONT_DIR = Path(__file__).parent / "fonts"
_BDF_SM = _FONT_DIR / "4x6.bdf"
_BDF_MD = _FONT_DIR / "5x8.bdf"
_CW_SM, _CW_MD = 4, 5

_gfx = _hw_sm = _hw_md = None
if USING_HARDWARE:
    try:
        from rgbmatrix import graphics as _gfx

        if _BDF_SM.exists():
            _hw_sm = _gfx.Font()
            _hw_sm.LoadFont(str(_BDF_SM))
        if _BDF_MD.exists():
            _hw_md = _gfx.Font()
            _hw_md.LoadFont(str(_BDF_MD))
    except Exception:
        _gfx = None


def _color(r, g, b):
    return _gfx.Color(r, g, b) if _gfx else (r, g, b)


def _draw_center(canvas, text, baseline_y, color, big):
    """Draw horizontally-centered text at a baseline. Uses the 5x8 font when
    *big*, else 4x6. Falls back to per-pixel/PIL on the mock canvas."""
    cw = _CW_MD if big else _CW_SM
    x = max(0, (MATRIX_W - len(text) * cw) // 2)
    font = _hw_md if big else _hw_sm
    if _gfx and font:
        _gfx.DrawText(canvas, font, x, baseline_y, color, text)
        return
    # Mock / no-graphics path: draw a simple block per character so the headless
    # PNG shows *something* legible-ish. Dev-only; hardware uses the BDF above.
    r, g, b = color if isinstance(color, tuple) else (255, 255, 255)
    top = baseline_y - (8 if big else 6)
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        cx = x + i * cw
        for yy in range(max(0, top), min(MATRIX_H, baseline_y)):
            for xx in range(cx, min(MATRIX_W, cx + cw - 1)):
                canvas.SetPixel(xx, yy, r, g, b)


def render_overlay(canvas, overlay) -> bool:
    """Render *overlay* over a blanked canvas. Returns True if it drew anything."""
    if not overlay or not isinstance(overlay, dict):
        return False

    kind = overlay.get("kind")
    canvas.Clear()

    if kind == "reset_prompt":
        secs = overlay.get("seconds_left")
        amber = _color(240, 160, 0)
        white = _color(255, 255, 255)
        _draw_center(canvas, "FACTORY", 9, amber, big=False)
        _draw_center(canvas, "RESET", 16, amber, big=False)
        if isinstance(secs, int):
            _draw_center(canvas, f"Hold {secs}s", 29, white, big=False)
        else:
            _draw_center(canvas, "Keep holding", 29, white, big=False)
        return True

    if kind == "reset_running":
        red = _color(230, 60, 60)
        _draw_center(canvas, "FACTORY", 14, red, big=True)
        _draw_center(canvas, "RESET", 26, red, big=True)
        return True

    # Unknown kind — treat as no overlay so we never wedge the display on a bad
    # value. Canvas was cleared; caller will render normally next frame.
    return False
