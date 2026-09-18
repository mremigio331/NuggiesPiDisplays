from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .common import _client, game_details_or_404, sort_games

router = APIRouter()


@router.get("/wnba/scoreboard")
async def wnba_scoreboard():
    games = sort_games(_client.get_wnba_scoreboard())
    return JSONResponse({"sport": "wnba", "games": games})


@router.get("/wnba/game/{event_id}")
async def wnba_game_details(event_id: str):
    details = game_details_or_404(_client.get_wnba_game_details, event_id)
    return JSONResponse(details)
