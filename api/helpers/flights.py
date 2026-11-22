"""Live planes near the saved flight spot, from free keyless ADS-B feeds.

Sources, tried in order until one answers:
  1. adsb.lol        https://api.adsb.lol/v2/point/{lat}/{lon}/{nm}
  2. adsb.fi         https://opendata.adsb.fi/api/v2/lat/{lat}/lon/{lon}/dist/{nm}
  3. OpenSky (anon)  https://opensky-network.org/api/states/all?lamin=..  (bbox)

All three are community services with no key and no uptime promise, so:
  * the upstream is called at most once per CACHE_TTL (60 s) per device, no
    matter how many callers (the panel and any open browser) ask;
  * one lock means concurrent callers share a single upstream call;
  * when every source fails, the last good answer is served (marked stale)
    for up to STALE_MAX before reporting an error.
"""

from __future__ import annotations

import logging
import math
import threading
import time

import requests

from helpers.aircraft_types import lookup as aircraft_lookup
from helpers.airlines import lookup as airline_lookup
from helpers.config import read_flight
from helpers.flight_routes import cached_route, request_route, route_status

logger = logging.getLogger(__name__)

CACHE_TTL = 60  # seconds between upstream calls
ROUTE_PREFETCH = 5  # nearest planes whose route is looked up ahead of time
STALE_MAX = 10 * 60  # how long a last good answer may stand in after failures
_TIMEOUT = 8
_MAX_POSITION_AGE = 60  # drop planes whose last position is older than this
_HEADERS = {
    "User-Agent": "NuggiesPiDisplays/1.0 (+https://github.com/mremigio331/NuggiesPiDisplays)",
    "Accept": "application/json",
}
_NM_PER_UNIT = {"mi": 0.868976, "km": 0.539957}
_UNIT_PER_NM = {"mi": 1.150779, "km": 1.852}
_COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

_lock = threading.Lock()
_cache: dict = {
    "key": None,  # (lat, lon, query radius nm) the planes were fetched for
    "aircraft": None,  # raw parsed planes from the last good fetch
    "source": None,
    "fetched_at": 0.0,  # last good fetch
    "attempted_at": 0.0,  # last upstream attempt, good or bad
    "error": None,
}


def invalidate() -> None:
    """Drop the cache so the next caller fetches for the new spot right away."""
    with _lock:
        _cache.update(
            key=None,
            aircraft=None,
            source=None,
            fetched_at=0.0,
            attempted_at=0.0,
            error=None,
        )


# ── Geometry ─────────────────────────────────────────────────────────────


def _distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3440.065  # earth radius in nautical miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Degrees clockwise from north, from point 1 toward point 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _compass(deg: float) -> str:
    return _COMPASS[int((deg + 22.5) // 45) % 8]


def _num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value:  # NaN
        return None
    return value


# ── Sources ──────────────────────────────────────────────────────────────


def _get_json(url: str, params: dict | None = None) -> dict:
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _parse_readsb(payload: dict) -> list[dict]:
    """adsb.lol and adsb.fi both return the readsb "ac" format."""
    planes = []
    for a in payload.get("ac") or payload.get("aircraft") or []:
        if not isinstance(a, dict):
            continue
        lat, lon = _num(a.get("lat")), _num(a.get("lon"))
        if lat is None or lon is None:
            continue
        if a.get("alt_baro") == "ground":
            continue
        seen = _num(a.get("seen_pos"))
        if seen is not None and seen > _MAX_POSITION_AGE:
            continue
        alt = _num(a.get("alt_baro"))
        if alt is None:
            alt = _num(a.get("alt_geom"))
        speed = _num(a.get("gs"))
        track = _num(a.get("track"))
        if track is None:
            track = _num(a.get("true_heading"))
        vrate = _num(a.get("baro_rate"))
        if vrate is None:
            vrate = _num(a.get("geom_rate"))
        planes.append(
            {
                "hex": str(a.get("hex") or "").strip().lower(),
                "callsign": str(a.get("flight") or "").strip(),
                "registration": str(a.get("r") or "").strip(),
                "type": str(a.get("t") or "").strip(),
                "description": str(a.get("desc") or "").strip(),
                "operator": str(a.get("ownOp") or "").strip(),
                "altitude_ft": round(alt) if alt is not None else None,
                "speed_kt": round(speed) if speed is not None else None,
                "track": round(track) if track is not None else None,
                "vertical_rate_fpm": round(vrate) if vrate is not None else None,
                "squawk": str(a.get("squawk") or "").strip(),
                "category": str(a.get("category") or "").strip().upper(),
                "latitude": lat,
                "longitude": lon,
            }
        )
    return planes


def _fetch_adsb_lol(lat: float, lon: float, nm: int) -> list[dict]:
    return _parse_readsb(_get_json(f"https://api.adsb.lol/v2/point/{lat}/{lon}/{nm}"))


def _fetch_adsb_fi(lat: float, lon: float, nm: int) -> list[dict]:
    return _parse_readsb(
        _get_json(f"https://opendata.adsb.fi/api/v2/lat/{lat}/lon/{lon}/dist/{nm}")
    )


def _fetch_opensky(lat: float, lon: float, nm: int) -> list[dict]:
    """Anonymous OpenSky takes a bounding box. Fewer fields (no type or
    registration); the caller trims the box corners back to the circle."""
    dlat = nm / 60.0
    dlon = nm / (60.0 * max(math.cos(math.radians(lat)), 0.01))
    params = {
        "lamin": max(-90.0, lat - dlat),
        "lamax": min(90.0, lat + dlat),
        "lomin": max(-180.0, lon - dlon),
        "lomax": min(180.0, lon + dlon),
    }
    payload = _get_json("https://opensky-network.org/api/states/all", params)
    planes = []
    for s in payload.get("states") or []:
        if not isinstance(s, list) or len(s) < 15:
            continue
        if s[8]:  # on the ground
            continue
        plon, plat = _num(s[5]), _num(s[6])
        if plat is None or plon is None:
            continue
        alt_m = _num(s[7])
        if alt_m is None:
            alt_m = _num(s[13])
        speed_ms, track, vrate_ms = _num(s[9]), _num(s[10]), _num(s[11])
        planes.append(
            {
                "hex": str(s[0] or "").strip().lower(),
                "callsign": str(s[1] or "").strip(),
                "registration": "",
                "type": "",
                "description": "",
                "operator": "",
                "altitude_ft": round(alt_m * 3.28084) if alt_m is not None else None,
                "speed_kt": (
                    round(speed_ms * 1.943844) if speed_ms is not None else None
                ),
                "track": round(track) if track is not None else None,
                "vertical_rate_fpm": (
                    round(vrate_ms * 196.8504) if vrate_ms is not None else None
                ),
                "squawk": str(s[14] or "").strip(),
                "latitude": plat,
                "longitude": plon,
            }
        )
    return planes


_SOURCES = (
    ("adsb.lol", _fetch_adsb_lol),
    ("adsb.fi", _fetch_adsb_fi),
    ("OpenSky", _fetch_opensky),
)


def _fetch_any(lat: float, lon: float, nm: int) -> tuple[list[dict], str]:
    errors = []
    for name, fetch in _SOURCES:
        try:
            return fetch(lat, lon, nm), name
        except Exception as e:
            logger.warning(f"Flight source {name} failed: {e}")
            errors.append(f"{name}: {e}")
    raise RuntimeError("; ".join(errors))


# ── Public ───────────────────────────────────────────────────────────────


def _shape(planes: list[dict], cfg: dict) -> list[dict]:
    """Add distance and direction from the spot, keep the circle, sort nearest first."""
    lat, lon, units = cfg["latitude"], cfg["longitude"], cfg["units"]
    limit_nm = cfg["radius"] * _NM_PER_UNIT[units]
    out = []
    for p in planes:
        d_nm = _distance_nm(lat, lon, p["latitude"], p["longitude"])
        if d_nm > limit_nm:
            continue
        brg = _bearing(lat, lon, p["latitude"], p["longitude"])
        aircraft = aircraft_lookup(p["type"])
        out.append(
            {
                **p,
                "distance_nm": round(d_nm, 2),
                "distance": round(d_nm * _UNIT_PER_NM[units], 1),
                "bearing": round(brg),
                "direction": _compass(brg),
                "airline": airline_lookup(p["callsign"]),
                "aircraft": aircraft,
                # A helicopter says so in its broadcast (category A7), or by type.
                "helicopter": p.get("category") == "A7"
                or bool(aircraft and aircraft["helicopter"]),
            }
        )
    out.sort(key=lambda p: p["distance_nm"])
    return out


def get_nearby() -> tuple[dict, int]:
    """Planes around the saved spot. Returns (body, HTTP status)."""
    cfg = read_flight()
    base = {
        "configured": cfg["latitude"] is not None,
        "location": {
            "latitude": cfg["latitude"],
            "longitude": cfg["longitude"],
            "label": cfg["location_label"],
        },
        "radius": cfg["radius"],
        "units": cfg["units"],
        "airlines_only": cfg["airlines_only"],
    }
    if not base["configured"]:
        return base, 200

    lat, lon = cfg["latitude"], cfg["longitude"]
    query_nm = max(1, math.ceil(cfg["radius"] * _NM_PER_UNIT[cfg["units"]]))
    key = (lat, lon, query_nm)

    with _lock:
        now = time.time()
        same_spot = _cache["key"] == key
        if not same_spot or now - _cache["attempted_at"] >= CACHE_TTL:
            _cache["attempted_at"] = now
            try:
                planes, source = _fetch_any(lat, lon, query_nm)
                _cache.update(
                    key=key,
                    aircraft=planes,
                    source=source,
                    fetched_at=now,
                    error=None,
                )
            except Exception as e:
                logger.error(f"All flight sources failed: {e}")
                if not same_spot:
                    # Never show planes from an old spot for a new one.
                    _cache.update(key=key, aircraft=None, source=None, fetched_at=0.0)
                _cache["error"] = "Flight data is unavailable right now"
        snapshot = dict(_cache)

    age = time.time() - snapshot["fetched_at"]
    if snapshot["aircraft"] is None or age > STALE_MAX:
        return {**base, "error": snapshot["error"] or "No flight data yet"}, 503

    aircraft = _shape(snapshot["aircraft"], cfg)
    hidden = 0
    if cfg["airlines_only"]:
        # An airline flight's callsign starts with a known airline code
        # (ASA414, DAL629). Private planes use their registration (N88MP).
        shown = [p for p in aircraft if p["airline"]]
        hidden = len(aircraft) - len(shown)
        aircraft = shown
    # Routes: every plane gets what is already cached (no network). The
    # nearest few are looked up in the background if not cached, so a plane
    # that becomes the closest usually has its route ready. route_status
    # tells "still looking" apart from "there is no route".
    for i, p in enumerate(aircraft):
        p["route"] = request_route(p) if i < ROUTE_PREFETCH else cached_route(p)
        p["route_status"] = route_status(p)
        if p["route"] and "flown_nm" in p["route"]:
            per = _UNIT_PER_NM[cfg["units"]]
            p["route"]["flown"] = round(p["route"]["flown_nm"] * per)
            p["route"]["to_go"] = round(p["route"]["to_go_nm"] * per)
    return {
        **base,
        "source": snapshot["source"],
        "fetched_at": round(snapshot["fetched_at"]),
        "age_seconds": round(age),
        "stale": snapshot["error"] is not None,
        "count": len(aircraft),
        "hidden": hidden,
        "closest": aircraft[0] if aircraft else None,
        "aircraft": aircraft,
    }, 200


def find_plane(hex_id: str) -> dict | None:
    """A plane from the last fetch, by its ICAO hex (no network)."""
    hex_id = (hex_id or "").strip().lower()
    with _lock:
        planes = _cache["aircraft"] or []
        return next((dict(p) for p in planes if p["hex"] == hex_id), None)
