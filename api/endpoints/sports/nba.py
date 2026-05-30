from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .common import _client, game_details_or_404, sort_games

router = APIRouter()


@router.get("/nba/scoreboard")
async def nba_scoreboard():
    games = sort_games(_client.get_nba_scoreboard())
    return JSONResponse({"sport": "nba", "games": games})


@router.get("/nba/game/{event_id}")
async def nba_game_details(event_id: str):
    details = game_details_or_404(_client.get_nba_game_details, event_id)
    return JSONResponse(details)
