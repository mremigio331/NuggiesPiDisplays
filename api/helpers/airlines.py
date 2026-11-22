"""Airline name and flight number from a callsign.

An airline flight's callsign is its 3-letter ICAO airline code plus the
flight number: DAL629 is Delta flight 629, written DL 629 on a ticket.

The code list is api/data/airlines.json, built from OpenFlights
(https://openflights.org/data, Open Database License). It keeps active
airlines, and defunct ones that still have an IATA code, because a defunct
ICAO code with no IATA code is often reused by someone else.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_FILE = Path(__file__).resolve().parents[1] / "data" / "airlines.json"
_CALLSIGN_RE = re.compile(r"^([A-Z]{3})0*([0-9]{1,4}[A-Z]{0,2})$")
# Words dropped to make a name fit next to the logo: "Delta Air Lines" -> "Delta".
_SUFFIXES = ("Air Lines", "Airlines", "Airways", "Airline", "Inc.", "Inc", "Ltd")
SHORT_NAME_MAX = 11  # letters that fit beside a 16 px logo in the small font


def _load() -> dict[str, list]:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))["airlines"]
    except Exception as e:
        logger.error(f"Could not load airline list {_FILE}: {e}")
        return {}


_AIRLINES = _load()


def short_name(name: str) -> str:
    short = name.strip()
    for suffix in _SUFFIXES:
        if short.endswith(" " + suffix) and len(short) > len(suffix) + 1:
            short = short[: -len(suffix)].strip()
            break
    if len(short) <= SHORT_NAME_MAX:
        return short
    words, out = short.split(), ""
    for w in words:
        nxt = f"{out} {w}".strip()
        if len(nxt) > SHORT_NAME_MAX:
            break
        out = nxt
    return out or short[:SHORT_NAME_MAX]


def lookup(callsign: str | None) -> dict | None:
    """Airline info for an airline callsign, or None (private plane, unknown code)."""
    m = _CALLSIGN_RE.match((callsign or "").strip().upper())
    if not m:
        return None
    icao, number = m.groups()
    entry = _AIRLINES.get(icao)
    if not entry:
        return None
    iata, name = entry[0], entry[1]
    return {
        "icao": icao,
        "iata": iata,
        "name": name,
        "short_name": short_name(name),
        "number": number,
        # What a ticket says: DL 629. ICAO code when there is no IATA code.
        "flight_number": f"{iata or icao} {number}",
    }
