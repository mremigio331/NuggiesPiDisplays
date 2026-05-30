from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .common import _client, game_details_or_404, sort_games

router = APIRouter()


@router.get("/nhl/scoreboard")
async def nhl_scoreboard():
    games = sort_games(_client.get_nhl_scoreboard())
    return JSONResponse({"sport": "nhl", "games": games})


@router.get("/nhl/game/{event_id}")
async def nhl_game_details(event_id: str):
    details = game_details_or_404(_client.get_nhl_game_details, event_id)
    return JSONResponse(details)
