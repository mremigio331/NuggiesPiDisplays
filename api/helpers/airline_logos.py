"""Airline logos, by IATA code, sized for the panel (16 px) or the website.

Sources, free and keyless, tried in order:
  1. https://images.kiwi.com/airlines/64/{IATA}.png
  2. https://pics.avs.io/64/64/{IATA}.png
Each logo is fetched once per device and saved to api/data/airline_logos/.
A white or light grey background touching the edge is turned black, so a
logo does not light up a bright square on the panel. A missing logo is not
asked for again for a day.
"""

from __future__ import annotations

import io
import logging
import os
import re
import threading
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_DIR = Path(__file__).resolve().parents[1] / "data" / "airline_logos"
_SOURCES = (
    "https://images.kiwi.com/airlines/64/{code}.png",
    "https://pics.avs.io/64/64/{code}.png",
)
_HEADERS = {
    "User-Agent": "NuggiesPiDisplays/1.0 (+https://github.com/mremigio331/NuggiesPiDisplays)"
}
_CODE_RE = re.compile(r"^[A-Z0-9]{2}$")
_MISS_TTL = 24 * 60 * 60
SIZES = (16, 32, 64)

_lock = threading.Lock()
_missing: dict[str, float] = {}  # code -> when no source had it


def valid_code(code: str) -> bool:
    return bool(_CODE_RE.match(code or ""))


def _blacken_background(img):
    """Flood-fill light pixels connected to the edge with black."""
    px = img.load()
    w, h = img.size
    seen = set()
    stack = [(x, y) for x in range(w) for y in (0, h - 1)]
    stack += [(x, y) for y in range(h) for x in (0, w - 1)]
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h):
            continue
        seen.add((x, y))
        r, g, b = px[x, y]
        if min(r, g, b) < 200 or max(r, g, b) - min(r, g, b) > 30:
            continue  # not white or light grey: part of the logo
        px[x, y] = (0, 0, 0)
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return img


def _download(code: str) -> bytes | None:
    from PIL import Image  # imported here so the API starts even without Pillow

    for src in _SOURCES:
        try:
            resp = requests.get(src.format(code=code), headers=_HEADERS, timeout=10)
            if resp.status_code != 200 or not resp.content:
                continue
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
            bg.alpha_composite(img)
            img = _blacken_background(bg.convert("RGB")).resize((64, 64), Image.LANCZOS)
            out = io.BytesIO()
            img.save(out, "PNG")
            return out.getvalue()
        except Exception as e:
            logger.warning(f"Logo source failed for {code} ({src}): {e}")
    return None


def get_logo(code: str, size: int = 64) -> bytes | None:
    """PNG bytes for airline *code* at *size* px square, or None."""
    code = (code or "").upper()
    if not valid_code(code) or size not in SIZES:
        return None
    path = _DIR / f"{code}.png"
    with _lock:
        if not path.exists():
            if time.time() - _missing.get(code, 0) < _MISS_TTL:
                return None
            data = _download(code)
            if not data:
                _missing[code] = time.time()
                return None
            _DIR.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, path)  # atomic: never a half-written logo
    try:
        from PIL import Image

        img = Image.open(path).convert("RGB")
        if size != 64:
            img = img.resize((size, size), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()
    except Exception as e:
        logger.warning(f"Bad cached logo {path}: {e}")
        path.unlink(missing_ok=True)
        return None
