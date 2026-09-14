"""Team list per league — powers the favourite-team picker.

Replaces hardcoded abbreviation lists in the web UI: every league gets its real
teams, with the ESPN ids that favourites are stored under.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .common import _client
from .update_settings import VALID_SPORTS

router = APIRouter()


@router.get("/teams")
async def get_teams(sport: str):
    """Teams in a league, keyed by the sport (which encodes the league)."""
    if sport not in VALID_SPORTS:
        return JSONResponse(
            {"error": f"sport must be one of {sorted(VALID_SPORTS)}"}, status_code=422
        )
    teams = _client.get_teams(sport)
    return JSONResponse({"sport": sport, "teams": teams})
