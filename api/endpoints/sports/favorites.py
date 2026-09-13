"""Favourite team endpoints — one set of teams per sport.

Teams are stored by ESPN team id under their sport (see _favorites), so the
league is always explicit. Each call returns the full sports settings section,
matching PUT /sports/settings and the lock endpoints.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from helpers.config import read_settings, write_settings

from . import _favorites
from .update_settings import VALID_SPORTS

logger = logging.getLogger(__name__)
router = APIRouter()


class FavoriteBody(BaseModel):
    # League the team belongs to; defaults to the selected sport
    sport: str | None = None


class FavoritesBody(BaseModel):
    team_ids: list[str]
    sport: str | None = None


def _resolve_sport(sports: dict, requested: str | None):
    """Return (sport, error_response). Falls back to the selected sport."""
    sport = requested or sports.get("sport", "")
    if not sport:
        return None, JSONResponse({"error": "no sport selected"}, status_code=422)
    if sport not in VALID_SPORTS:
        return None, JSONResponse(
            {"error": f"sport must be one of {sorted(VALID_SPORTS)}"}, status_code=422
        )
    return sport, None


@router.get("/favorites")
async def get_favorites():
    """Favourite team ids for every sport."""
    sports = read_settings().get("sports", {})
    return JSONResponse({"favorite_teams": _favorites.read_all(sports)})


@router.put("/favorites")
async def set_favorites(body: FavoritesBody):
    """Replace one sport's favourites wholesale."""
    settings = read_settings()
    sports = settings.setdefault("sports", {})
    sport, error = _resolve_sport(sports, body.sport)
    if error:
        return error
    invalid = [t for t in body.team_ids if not _favorites.valid_team_id(str(t).upper())]
    if invalid:
        return JSONResponse({"error": f"invalid team ids: {invalid}"}, status_code=422)

    favorites = _favorites.set_for(sports, sport, body.team_ids)
    write_settings(settings)
    logger.info(f"Favourite {sport} teams set to {favorites[sport]}")
    return JSONResponse(sports)


@router.put("/favorites/{team_id}")
async def add_favorite(team_id: str, body: FavoriteBody | None = None):
    """Add one team to a sport's favourites."""
    if not _favorites.valid_team_id(team_id.upper()):
        return JSONResponse(
            {
                "error": f"team_id must be alphanumeric, {_favorites.MAX_ID_LEN} chars max"
            },
            status_code=422,
        )
    settings = read_settings()
    sports = settings.setdefault("sports", {})
    sport, error = _resolve_sport(sports, body.sport if body else None)
    if error:
        return error

    favorites = _favorites.add(sports, sport, team_id)
    write_settings(settings)
    logger.info(f"Favourited {sport} team {team_id}; now {favorites[sport]}")
    return JSONResponse(sports)


@router.delete("/favorites/{team_id}")
async def remove_favorite(team_id: str, sport: str | None = None):
    """Remove one team from a sport's favourites."""
    settings = read_settings()
    sports = settings.setdefault("sports", {})
    resolved, error = _resolve_sport(sports, sport)
    if error:
        return error

    favorites = _favorites.remove(sports, resolved, team_id)
    write_settings(settings)
    logger.info(f"Unfavourited {resolved} team {team_id}; now {favorites[resolved]}")
    return JSONResponse(sports)
