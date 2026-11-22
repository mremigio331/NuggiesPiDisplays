"""Aircraft type names from the ICAO type code a plane sends (B39M, A321).

The list is api/data/aircraft_types.json, built from tar1090-db
(https://github.com/wiedehopf/tar1090-db), which comes from the Mictronics
aircraft database (https://www.mictronics.de/aircraft-database/).
Names there read "BOEING 737 MAX 9"; this splits them into a maker
("Boeing") and a model ("737 MAX 9") for the panel.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_FILE = Path(__file__).resolve().parents[1] / "data" / "aircraft_types.json"
# Makers whose name is two words in the list.
_TWO_WORD_MAKERS = {
    "DE HAVILLAND",
    "MCDONNELL DOUGLAS",
    "BRITISH AEROSPACE",
    "AIRBUS HELICOPTERS",
}
# Title case gets these wrong.
_MAKER_SPELLING = {
    "MCDONNELL DOUGLAS": "McDonnell Douglas",
    "MCDONNELL-DOUGLAS": "McDonnell Douglas",
}


def _load() -> dict[str, str]:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))["types"]
    except Exception as e:
        logger.error(f"Could not load aircraft type list {_FILE}: {e}")
        return {}


_TYPES = _load()


def _maker_name(raw: str) -> str:
    if raw in _MAKER_SPELLING:
        return _MAKER_SPELLING[raw]
    # Short all-caps makers are acronyms (ATR, IAI); keep them as is.
    return raw if len(raw) <= 3 else raw.title()


def lookup(code: str | None) -> dict | None:
    """{"code", "name", "maker", "model", "helicopter"} for a type code, or None."""
    code = (code or "").strip().upper()
    entry = _TYPES.get(code)
    if not entry:
        return None
    # [name, class]; class is the ICAO description's first letter.
    full, cls = (entry, "") if isinstance(entry, str) else (entry[0], entry[1])
    words = full.split()
    # A bare "ATR-72-600" is maker ATR, model 72-600.
    if len(words) == 1 and re.match(r"^[A-Z]+-", words[0]):
        words = words[0].split("-", 1)
    n = 2 if " ".join(words[:2]) in _TWO_WORD_MAKERS else 1
    maker = _maker_name(" ".join(words[:n]))
    # "ERJ-170-200 (long wing)" -> "ERJ-170-200": the panel has 15 letters.
    model = re.sub(r"\s*\(.*?\)", "", " ".join(words[n:])).strip()
    return {
        "code": code,
        "name": f"{maker} {model}".strip(),
        "maker": maker,
        "model": model or code,
        "helicopter": cls == "H",
    }
