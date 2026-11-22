"""Flight display renderer for the 64x32 matrix.

Screens:
  plane      the closest plane. Top: airline logo (16x16) with the airline
             name and flight number beside it. Bottom: the start airport,
             then the end airport, then the aircraft (Boeing / 737 MAX 9),
             then the distance flown and to go, 5 seconds each. No route
             known: "No route info" and the aircraft name.
  setup      no spot saved: "Update settings to view flight info"
  empty      spot saved, nothing in the air inside the radius
  error      the API or every flight feed is down

A plane with no airline (private, small) gets a plane or helicopter icon and
its callsign instead of a logo and flight number.

Text is drawn pixel by pixel from the same BDF fonts the other modes use, so
the panel and the headless PNG look the same.
"""

from __future__ import annotations

from pathlib import Path

import bdf

W, H = 64, 32
LOGO = 16  # logo size in pixels
TEXT_X = LOGO + 2

_FONT_DIR = Path(__file__).parent.parent / "fonts"
_SMALL = bdf.load(_FONT_DIR / "4x6.bdf")
_LARGE = bdf.load(_FONT_DIR / "5x8.bdf")

# Saturated colors: on this panel mid-level colors read as white.
WHITE = (255, 255, 255)
GREY = (90, 90, 90)
BLUE = (0, 120, 255)
CYAN = (0, 220, 220)
YELLOW = (255, 190, 0)
RED = (230, 30, 30)

# A 16x16 plane seen from above, nose up: drawn where a logo would be.
_PLANE_ICON = (
    "................",
    ".......##.......",
    ".......##.......",
    ".......##.......",
    "......####......",
    "....########....",
    "..############..",
    ".##############.",
    ".......##.......",
    ".......##.......",
    ".......##.......",
    ".......##.......",
    ".....######.....",
    "....########....",
    "................",
    "................",
)

# A 16x16 helicopter seen from above: rotor blades (+) over the body (#),
# tail boom down to the tail rotor.
_HELI_ICON = (
    "................",
    ".+............+.",
    "..+....##....+..",
    "...+..####..+...",
    "....+######+....",
    ".....######.....",
    ".....######.....",
    "....+######+....",
    "...+..####..+...",
    "..+....##....+..",
    ".+.....##.....+.",
    ".......##.......",
    ".......##.......",
    ".....######.....",
    ".......##.......",
    "................",
)

PHASE_SECONDS = 5  # how long each bottom screen (From, To, Aircraft, Flown) shows


def _text_width(font, text: str) -> int:
    return sum(
        font.glyphs[ord(c)].dwidth if ord(c) in font.glyphs else font.default_dwidth
        for c in text
    )


def _fit(font, text: str, max_w: int) -> str:
    while text and _text_width(font, text) > max_w:
        text = text[:-1]
    return text.rstrip()


def _fit_words(font, text: str, max_w: int) -> str:
    """Like _fit, but drops whole words (CESSNA 172 Skyhawk -> CESSNA 172)."""
    if _text_width(font, text) <= max_w:
        return text
    words, out = text.split(), ""
    for w in words:
        nxt = f"{out} {w}".strip()
        if _text_width(font, nxt) > max_w:
            break
        out = nxt
    return out or _fit(font, text, max_w)


def _text(canvas, font, x: int, baseline: int, text: str, color) -> int:
    pen = x
    r, g, b = color
    for ch in text:
        glyph = font.glyphs.get(ord(ch))
        if glyph is None:
            pen += font.default_dwidth
            continue
        top = baseline - glyph.bbyoff - glyph.bbh
        for ry, bits in enumerate(glyph.rows):
            for cx in range(glyph.bbw):
                if bits & (1 << (glyph.bbw - 1 - cx)):
                    px, py = pen + glyph.bbxoff + cx, top + ry
                    if 0 <= px < W and 0 <= py < H:
                        canvas.SetPixel(px, py, r, g, b)
        pen += glyph.dwidth
    return pen


def _center(canvas, font, baseline: int, text: str, color) -> None:
    text = _fit(font, text, W)
    _text(canvas, font, (W - _text_width(font, text)) // 2, baseline, text, color)


def _draw_logo(canvas, logo) -> None:
    """*logo* is a 16x16 RGB PIL image."""
    px = logo.load()
    for y in range(LOGO):
        for x in range(LOGO):
            r, g, b = px[x, y][:3]
            if r or g or b:
                canvas.SetPixel(x, y, r, g, b)


def _draw_plane_icon(canvas, helicopter: bool = False) -> None:
    for y, row in enumerate(_HELI_ICON if helicopter else _PLANE_ICON):
        for x, c in enumerate(row):
            if c == "#":
                canvas.SetPixel(x, y, *BLUE)
            elif c == "+":
                canvas.SetPixel(x, y, *CYAN)


def _plane_name(plane: dict) -> str:
    return (
        plane.get("callsign")
        or plane.get("registration")
        or (plane.get("hex") or "").upper()
        or "Unknown"
    )


def _has_route(plane: dict) -> bool:
    route = plane.get("route")
    return (
        isinstance(route, dict)
        and isinstance(route.get("origin"), dict)
        and isinstance(route.get("destination"), dict)
    )


def _has_flown(plane: dict) -> bool:
    return _has_route(plane) and isinstance(plane["route"].get("flown"), (int, float))


def bottom_steps(plane: dict) -> list[str]:
    """The bottom screens a plane cycles through, PHASE_SECONDS each."""
    if not _has_route(plane):
        # Still looking the route up: show the aircraft until it arrives, so
        # the panel never says "No route info" for a route that is coming.
        if plane.get("route_status") == "pending" and (
            plane.get("aircraft") or plane.get("type")
        ):
            return ["aircraft"]
        return ["none"]
    steps = ["from", "to"]
    if plane.get("aircraft") or plane.get("type"):
        steps.append("aircraft")
    if _has_flown(plane):
        steps.append("flown")
    return steps


def phase_count(data: dict | None) -> int:
    """How many bottom screens the closest plane cycles through. 1 = no cycle."""
    closest = (data or {}).get("closest")
    return len(bottom_steps(closest)) if closest else 1


def _airport_block(canvas, label: str, airport: dict) -> None:
    code = airport.get("iata") or airport.get("icao") or "?"
    place = airport.get("location") or airport.get("name") or ""
    pen = _text(canvas, _SMALL, 1, 25, label, GREY)
    _text(canvas, _LARGE, pen + 3, 25, _fit(_LARGE, code, W - pen - 3), WHITE)
    _text(canvas, _SMALL, 1, 31, _fit(_SMALL, place, W - 2), CYAN)


def _flown_block(canvas, route: dict, units: str) -> None:
    pen = _text(canvas, _SMALL, 1, 25, "Flown", GREY)
    flown = f"{route['flown']:,}{units}"
    _text(canvas, _LARGE, pen + 3, 25, _fit(_LARGE, flown, W - pen - 3), WHITE)
    _text(canvas, _SMALL, 1, 31, f"{route['to_go']:,}{units} to go", CYAN)


def _aircraft(plane: dict) -> dict:
    """The type-list entry (maker, model, name), or {} if the type is unknown."""
    return plane.get("aircraft") if isinstance(plane.get("aircraft"), dict) else {}


def _aircraft_text(plane: dict) -> str:
    """Boeing 737 MAX 9, else the feed's description, else the code."""
    aircraft = _aircraft(plane)
    return aircraft.get("name") or plane.get("description") or plane.get("type") or ""


def _fit_aircraft(font, plane: dict, max_w: int) -> str:
    """The aircraft name that fits. When only the maker would fit ("Airbus"
    from "Airbus Helicopters EC-135/635"), the model says more."""
    aircraft = _aircraft(plane)
    text = _fit_words(font, _aircraft_text(plane), max_w)
    maker, model = aircraft.get("maker") or "", aircraft.get("model") or ""
    if model and maker and len(text) <= len(maker):
        return _fit_words(font, model, max_w)
    return text


def _aircraft_block(canvas, plane: dict) -> None:
    """Maker big (Boeing), model under it (737 MAX 9)."""
    aircraft = _aircraft(plane)
    top = aircraft.get("maker") or plane.get("type") or ""
    bottom = aircraft.get("model") or plane.get("description") or ""
    _text(canvas, _LARGE, 1, 25, _fit_words(_LARGE, top, W - 2), WHITE)
    _text(canvas, _SMALL, 1, 31, _fit_words(_SMALL, bottom, W - 2), CYAN)


def _no_route_block(canvas, plane: dict) -> None:
    _text(canvas, _SMALL, 1, 25, "No route info", GREY)
    _text(canvas, _SMALL, 1, 31, _fit_aircraft(_SMALL, plane, W - 2), BLUE)


def render_plane(canvas, plane: dict, units: str, phase: int = 0, logo=None) -> None:
    airline = plane.get("airline") if isinstance(plane.get("airline"), dict) else None
    width = W - TEXT_X

    # ── Top: logo, then airline name over flight number.
    if logo is not None:
        _draw_logo(canvas, logo)
    else:
        _draw_plane_icon(canvas, bool(plane.get("helicopter")))
    if airline:
        name = airline.get("short_name") or airline.get("name") or ""
        number = airline.get("flight_number") or _plane_name(plane)
    else:
        name = _fit_aircraft(_SMALL, plane, width)
        number = _plane_name(plane)
    _text(canvas, _SMALL, TEXT_X, 6, _fit_words(_SMALL, name, width), CYAN)
    _text(canvas, _LARGE, TEXT_X, 15, _fit(_LARGE, number, width), YELLOW)

    # ── Bottom: start airport, end airport, aircraft, distance flown, each
    #    PHASE_SECONDS. With no route: "No route info" and the aircraft.
    steps = bottom_steps(plane)
    step = steps[phase % len(steps)]
    if step == "none":
        _no_route_block(canvas, plane)
    elif step == "from":
        _airport_block(canvas, "From", plane["route"]["origin"])
    elif step == "to":
        _airport_block(canvas, "To", plane["route"]["destination"])
    elif step == "aircraft":
        _aircraft_block(canvas, plane)
    else:
        _flown_block(canvas, plane["route"], units)


def render_setup(canvas) -> None:
    _center(canvas, _SMALL, 10, "Update settings", WHITE)
    _center(canvas, _SMALL, 18, "to view", WHITE)
    _center(canvas, _SMALL, 26, "flight info", WHITE)


def render_empty(canvas, radius, units: str, airlines_only: bool = False) -> None:
    _center(canvas, _LARGE, 13, "No flights" if airlines_only else "No planes", WHITE)
    _center(canvas, _SMALL, 24, f"within {radius}{units}", GREY)


def render_error(canvas) -> None:
    _center(canvas, _SMALL, 13, "Flight data", RED)
    _center(canvas, _SMALL, 21, "unavailable", RED)


def render_loading(canvas) -> None:
    _center(canvas, _SMALL, 13, "Looking for", WHITE)
    _center(canvas, _SMALL, 21, "planes...", WHITE)


def render(canvas, data: dict | None, phase: int = 0, logo=None) -> str:
    """Draw the right screen for *data* (the /flight/nearby body, or None when
    the API could not be reached). *phase* picks the bottom screen (see
    bottom_steps); *logo* is the closest plane's airline logo, if any.
    Returns the screen name, for logging."""
    canvas.Clear()
    if data is None:
        render_error(canvas)
        return "error"
    if not data.get("configured"):
        render_setup(canvas)
        return "setup"
    if data.get("aircraft") is None:
        render_error(canvas)
        return "error"
    closest = data.get("closest")
    units = data.get("units") or "mi"
    if not closest:
        render_empty(canvas, data.get("radius"), units, bool(data.get("airlines_only")))
        return "empty"
    render_plane(canvas, closest, units, phase, logo)
    return "plane"
