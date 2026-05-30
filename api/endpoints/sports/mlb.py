from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .common import _client, game_details_or_404, sort_games

router = APIRouter()


@router.get("/mlb/scoreboard")
async def mlb_scoreboard():
    games = sort_games(_client.get_mlb_scoreboard())
    return JSONResponse({"sport": "mlb", "games": games})


@router.get("/mlb/game/{event_id}")
async def mlb_game_details(event_id: str):
    details = game_details_or_404(_client.get_mlb_game_details, event_id)
    return JSONResponse(details)
