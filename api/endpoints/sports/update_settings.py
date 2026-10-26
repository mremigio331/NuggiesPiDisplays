import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import read_settings, write_settings

from . import _favorites, _locks
from .football import FOOTBALL_SPORTS
from .soccer import SOCCER_SPORTS

logger = logging.getLogger(__name__)
router = APIRouter()

# Real leagues. Extend this set when adding new sports. Football leagues (NFL,
# NCAAF, …) and soccer leagues (NWSL, …) are each their own sport and come from
# FOOTBALL_SPORTS / SOCCER_SPORTS. This is also the set of leagues a team may be
# favourited under — "favorites" is NOT a league, so it stays out of here.
VALID_SPORTS = {"nba", "wnba", "mlb", "nhl", *FOOTBALL_SPORTS, *SOCCER_SPORTS}

# The "favorites" pseudo-sport cycles games across every league that has
# favourites; it is selectable as the active sport but is not a real league.
FAVORITES_SPORT = "favorites"

# Sports the display can be switched to — real leagues plus the favourites feed.
SELECTABLE_SPORTS = VALID_SPORTS | {FAVORITES_SPORT}


# Human labels for the four core leagues that are NOT defined in the
# self-registering FOOTBALL_SPORTS / SOCCER_SPORTS dicts (those carry their own
# "name"). Keep this to the hardcoded core only — a new football/soccer league
# brings its own label, so it must NOT be added here.
_CORE_LEAGUE_LABELS = {
    "mlb": "MLB",
    "nba": "NBA",
    "wnba": "WNBA",
    "nhl": "NHL",
}


def sport_options() -> list[dict]:
    """Canonical {key,label} list of every selectable sport, Favorites first.

    This is THE source of truth for "which leagues can the display show and what
    are they called." It is assembled from the same self-registering league
    dicts the rest of sports uses (FOOTBALL_SPORTS / SOCCER_SPORTS carry their
    own "name"), plus the four core leagues' labels — so adding a league in ONE
    place (its dict) makes it appear everywhere that consumes this, including the
    schedule's league picker. Nothing downstream redefines the list.
    """
    labels = dict(_CORE_LEAGUE_LABELS)
    for key, cfg in {**FOOTBALL_SPORTS, **SOCCER_SPORTS}.items():
        labels[key] = cfg.get("name", key.upper())
    # Favorites pseudo-league first, then real leagues alphabetically by label.
    opts = [{"key": FAVORITES_SPORT, "label": "Favorites"}]
    opts += sorted(
        ({"key": k, "label": labels.get(k, k.upper())} for k in VALID_SPORTS),
        key=lambda o: o["label"].lower(),
    )
    return opts


_VALID_DISPLAY_MODES = {"focus", "overview"}


class SportsSettingsBody(BaseModel):
    # Favourite teams are per sport and keyed by ESPN team id — see
    # favorites.py for the endpoints that manage them.
    cycle_interval_seconds: int | None = None
    sport: str | None = None
    display_mode: str | None = None
    # One-shot "show this game now" — the display jumps to it, then resumes
    # cycling. The display consumes it once, so it is not cleared here.
    # Game locks are a list with timestamps; see locks.py.
    force_event_id: str | None = None


@router.put("/settings")
async def update_sports_settings(body: SportsSettingsBody):
    if body.cycle_interval_seconds is not None and not (
        5 <= body.cycle_interval_seconds <= 120
    ):
        return JSONResponse(
            {"error": "cycle_interval_seconds must be 5–120"}, status_code=422
        )
    if body.sport is not None and body.sport not in SELECTABLE_SPORTS:
        return JSONResponse(
            {"error": f"sport must be one of {sorted(SELECTABLE_SPORTS)}"},
            status_code=422,
        )
    if body.display_mode is not None and body.display_mode not in _VALID_DISPLAY_MODES:
        return JSONResponse(
            {"error": f"display_mode must be one of {sorted(_VALID_DISPLAY_MODES)}"},
            status_code=422,
        )
    if body.force_event_id and not _locks.valid_event_id(body.force_event_id):
        return JSONResponse(
            {
                "error": "force_event_id must be alphanumeric, "
                f"{_locks.MAX_EVENT_ID} chars max"
            },
            status_code=422,
        )

    settings = read_settings()
    sports = settings.setdefault("sports", {})
    if body.cycle_interval_seconds is not None:
        sports["cycle_interval_seconds"] = body.cycle_interval_seconds
    if body.sport is not None:
        # A pending one-shot jump belongs to the league it was requested from.
        # Locks carry their own sport, so they survive a league switch.
        if body.sport != sports.get("sport"):
            sports["force_event_id"] = ""
        sports["sport"] = body.sport
    if body.display_mode is not None:
        sports["display_mode"] = body.display_mode
    if body.force_event_id is not None:
        sports["force_event_id"] = body.force_event_id
    # Any write is a chance to persist normal form: drop expired locks and
    # store favourites as {sport: [team_id, …]}
    _locks.write(sports, _locks.read(sports))
    _favorites.write(sports, _favorites.read_all(sports))
    write_settings(settings)
    logger.info(f"Sports settings updated: {sports}")
    return JSONResponse(sports)
