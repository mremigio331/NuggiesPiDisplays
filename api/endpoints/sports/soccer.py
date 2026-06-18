from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .common import _client, game_details_or_404, sort_games

router = APIRouter()

# Allowlisted soccer leagues — ESPN league slugs
VALID_SOCCER_LEAGUES = {
    "fifa.world": "FIFA World Cup",
}


@router.get("/soccer/leagues")
async def soccer_leagues():
    """Return the allowlisted soccer leagues."""
    return JSONResponse(
        {"leagues": [{"key": k, "name": v} for k, v in VALID_SOCCER_LEAGUES.items()]}
    )


@router.get("/soccer/scoreboard")
async def soccer_scoreboard(league: str = "fifa.world"):
    if league not in VALID_SOCCER_LEAGUES:
        return JSONResponse(
            {"error": f"league must be one of {sorted(VALID_SOCCER_LEAGUES)}"},
            status_code=422,
        )
    games = sort_games(_client.get_soccer_scoreboard(league))
    return JSONResponse({"sport": "soccer", "league": league, "games": games})


@router.get("/soccer/game/{event_id}")
async def soccer_game_details(event_id: str, league: str = "fifa.world"):
    if league not in VALID_SOCCER_LEAGUES:
        return JSONResponse(
            {"error": f"league must be one of {sorted(VALID_SOCCER_LEAGUES)}"},
            status_code=422,
        )
    details = game_details_or_404(
        lambda eid: _client.get_soccer_game_details(eid, league), event_id
    )
    return JSONResponse(details)
