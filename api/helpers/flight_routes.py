"""Where a flight came from and where it is going, by callsign.

Source: adsb.lol's free route lookup, https://api.adsb.lol/api/0/route/{callsign}
(no key). It is a community list keyed by callsign, so:
  * only airline-style callsigns are looked up (3 letters + a number, like
    ASA414). Private planes (N123AB) have no route and are never asked about;
  * a route can list several stops (SJC-SEA-DAL-BNA). The leg being flown is
    picked from the plane's position and heading;
  * every answer, including "no route", is cached per callsign for a day,
    and saved to disk so restarts do not ask again. Network errors are
    retried after 10 minutes;
  * a lookup takes about 6 s, so the plane list never waits on one:
    request_route() starts it in the background and the route shows on the
    next poll. Only a website tap (get_route) waits for the answer.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

ROUTE_TTL = 24 * 60 * 60
ERROR_TTL = 10 * 60
_MAX_ENTRIES = 2000
_TIMEOUT = 15  # the route server takes about 6 s per lookup
_HEADERS = {
    "User-Agent": "NuggiesPiDisplays/1.0 (+https://github.com/mremigio331/NuggiesPiDisplays)",
    "Accept": "application/json",
}
_CALLSIGN_RE = re.compile(r"^[A-Z]{3}[0-9]{1,4}[A-Z]{0,2}$")
_CACHE_FILE = Path(__file__).resolve().parents[1] / "data" / "flight_routes.json"

_lock = threading.Lock()
# callsign -> {"at": epoch, "ttl": seconds, "airports": [...] | None,
#              "failed": True when the last lookup hit a network error}
_cache: dict[str, dict] = {}
_inflight: set[str] = set()  # callsigns being looked up right now


def _load() -> None:
    try:
        saved = json.loads(_CACHE_FILE.read_text())
        if isinstance(saved, dict):
            _cache.update(
                {k: v for k, v in saved.items() if isinstance(v, dict) and "at" in v}
            )
    except Exception:
        pass


def _save() -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_cache))
        os.replace(tmp, _CACHE_FILE)  # atomic: never a half-written file
    except Exception as e:
        logger.warning(f"Could not save flight route cache: {e}")


_load()


def lookupable(callsign: str | None) -> bool:
    return bool(callsign) and bool(_CALLSIGN_RE.match(callsign.strip().upper()))


def _airport(a: dict) -> dict | None:
    try:
        lat, lon = float(a["lat"]), float(a["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "iata": str(a.get("iata") or "").strip(),
        "icao": str(a.get("icao") or "").strip(),
        "name": str(a.get("name") or "").strip(),
        "location": str(a.get("location") or "").strip(),
        "latitude": lat,
        "longitude": lon,
    }


def _fetch(callsign: str) -> list[dict] | None:
    """The route's airports in order, or None when adsb.lol has no route.
    Raises on network errors so they are retried sooner."""
    resp = requests.get(
        f"https://api.adsb.lol/api/0/route/{callsign}",
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    airports = [_airport(a) for a in (resp.json().get("_airports") or [])]
    airports = [a for a in airports if a]
    return airports if len(airports) >= 2 else None


def _nm(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 3440.065 * math.asin(min(1.0, math.sqrt(a)))


def _bearing(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _pick_leg(airports: list[dict], plane: dict) -> tuple[dict, dict]:
    """The leg the plane is on: the one it sits closest to the straight line
    of, preferring legs whose destination is roughly ahead of the plane."""
    if len(airports) == 2:
        return airports[0], airports[1]
    lat, lon, track = plane.get("latitude"), plane.get("longitude"), plane.get("track")
    if lat is None or lon is None:
        return airports[0], airports[-1]
    best, best_score = (airports[0], airports[1]), math.inf
    for a, b in zip(airports, airports[1:]):
        leg = max(_nm(a["latitude"], a["longitude"], b["latitude"], b["longitude"]), 1)
        detour = (
            _nm(a["latitude"], a["longitude"], lat, lon)
            + _nm(lat, lon, b["latitude"], b["longitude"])
            - leg
        )
        score = detour / leg
        if isinstance(track, (int, float)):
            ahead = abs(
                (_bearing(lat, lon, b["latitude"], b["longitude"]) - track + 180) % 360
                - 180
            )
            if ahead > 90:
                score += 10  # flying away from this leg's destination
        if score < best_score:
            best, best_score = (a, b), score
    return best


def _public(a: dict) -> dict:
    return {k: a[k] for k in ("iata", "icao", "name", "location")}


def _route_for(airports: list[dict] | None, plane: dict) -> dict | None:
    if not airports:
        return None
    origin, dest = _pick_leg(airports, plane)
    route = {
        "origin": _public(origin),
        "destination": _public(dest),
        "stops": len(airports),
    }
    # Straight-line distances, so the real path flown is a little longer.
    lat, lon = plane.get("latitude"), plane.get("longitude")
    if lat is not None and lon is not None:
        route["flown_nm"] = round(
            _nm(origin["latitude"], origin["longitude"], lat, lon), 1
        )
        route["to_go_nm"] = round(_nm(lat, lon, dest["latitude"], dest["longitude"]), 1)
    return route


def cached_route(plane: dict) -> dict | None:
    """Route from the cache only (no network). None if unknown or no route."""
    cs = (plane.get("callsign") or "").strip().upper()
    with _lock:
        entry = _cache.get(cs)
    return _route_for(entry.get("airports") if entry else None, plane)


def route_status(plane: dict) -> str:
    """One of:
    known    the route is cached
    pending  being looked up, not asked yet, or the last lookup failed and
             will be retried (so the panel never claims there is no route)
    none     no route: a private plane, or adsb.lol has none for this flight
    """
    cs = (plane.get("callsign") or "").strip().upper()
    if not lookupable(cs):
        return "none"
    with _lock:
        entry = _cache.get(cs)
        if entry and entry.get("airports"):
            return "known"
        if cs in _inflight or not entry or entry.get("failed"):
            return "pending"
    return "none"


def _fresh(cs: str) -> bool:
    entry = _cache.get(cs)
    return bool(entry) and time.time() - entry["at"] < entry.get("ttl", ROUTE_TTL)


def _refresh(cs: str) -> None:
    """Look *cs* up and cache the answer. Network happens outside the lock."""
    try:
        try:
            airports, ttl, failed = _fetch(cs), ROUTE_TTL, False
        except Exception as e:
            logger.warning(f"Route lookup failed for {cs}: {e}")
            airports, ttl, failed = None, ERROR_TTL, True
        with _lock:
            if failed and cs in _cache:
                airports = _cache[cs].get("airports")  # keep the last good route
            _cache[cs] = {"at": time.time(), "ttl": ttl, "airports": airports}
            if failed:
                _cache[cs]["failed"] = True
            if len(_cache) > _MAX_ENTRIES:
                oldest = sorted(_cache, key=lambda k: _cache[k]["at"])
                for old in oldest[: len(_cache) - _MAX_ENTRIES]:
                    del _cache[old]
            _save()
    finally:
        with _lock:
            _inflight.discard(cs)  # never leave a callsign stuck as in flight


def _claim(cs: str) -> tuple[bool, bool]:
    """(needs a lookup, this caller should do it)."""
    with _lock:
        if _fresh(cs):
            return False, False
        if cs in _inflight:
            return True, False
        _inflight.add(cs)
        return True, True


def request_route(plane: dict) -> dict | None:
    """Cached route now; starts a background lookup if it is missing. Never
    blocks and never raises."""
    cs = (plane.get("callsign") or "").strip().upper()
    if not lookupable(cs):
        return None
    _, mine = _claim(cs)
    if mine:
        threading.Thread(target=_refresh, args=(cs,), daemon=True).start()
    return cached_route(plane)


def get_route(plane: dict) -> dict | None:
    """Route for *plane*, waiting for a lookup if needed (website tap)."""
    cs = (plane.get("callsign") or "").strip().upper()
    if not lookupable(cs):
        return None
    needed, mine = _claim(cs)
    if mine:
        _refresh(cs)
    elif needed:
        deadline = time.time() + _TIMEOUT + 2
        while time.time() < deadline:
            with _lock:
                if cs not in _inflight:
                    break
            time.sleep(0.2)
    return cached_route(plane)
