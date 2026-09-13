from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.config import read_settings

from . import _favorites, _locks

router = APIRouter()


@router.get("/settings")
async def get_sports_settings():
    """Sports settings, normalised for the client.

    Expired game locks are filtered out and favourite teams are returned as
    {sport: [team_id, …]} whatever shape is on disk. Filtering here rather than
    writing back keeps this a pure read — the display polls it every second.
    Both are persisted in normal form on the next settings write.
    """
    sports = dict(read_settings().get("sports", {}))
    sports["locked_games"] = _locks.read(sports)
    sports["favorite_teams"] = _favorites.read_all(sports)
    sports.pop("locked_event_id", None)  # superseded by locked_games
    return JSONResponse(sports)
