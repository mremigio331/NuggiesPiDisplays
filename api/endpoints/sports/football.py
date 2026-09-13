"""Football scoreboard routes — one sport per football league.

NFL and college football share ESPN's football endpoints and payload shape, so
the routes are built from a single factory. Each league is still its own sport:
NFL lives at `/sports/nfl/*`, NCAA football would live at `/sports/ncaaf/*`.

Adding NCAA football is one entry in FOOTBALL_SPORTS below — routes, settings
validation (see update_settings.py) and the display registry all read from it.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .common import _client, game_details_or_404, sort_games

# sport key → {league: ESPN league slug, name: human label}
FOOTBALL_SPORTS: dict[str, dict[str, str]] = {
    "nfl": {"league": "nfl", "name": "NFL"},
    # "ncaaf": {"league": "college-football", "name": "NCAA Football"},
}


def build_football_router(sport: str, league: str) -> APIRouter:
    """Return scoreboard + game-details routes for one football league."""
    league_router = APIRouter()

    @league_router.get(f"/{sport}/scoreboard", name=f"{sport}_scoreboard")
    async def football_scoreboard():
        games = sort_games(_client.get_football_scoreboard(league))
        return JSONResponse({"sport": sport, "league": league, "games": games})

    @league_router.get(f"/{sport}/game/{{event_id}}", name=f"{sport}_game_details")
    async def football_game_details(event_id: str):
        details = game_details_or_404(
            lambda eid: _client.get_football_game_details(eid, league), event_id
        )
        return JSONResponse(details)

    return league_router


router = APIRouter()


@router.get("/football/leagues")
async def football_leagues():
    """Return the football leagues available as sports."""
    return JSONResponse(
        {
            "leagues": [
                {"key": key, "name": cfg["name"]}
                for key, cfg in FOOTBALL_SPORTS.items()
            ]
        }
    )


for _sport, _cfg in FOOTBALL_SPORTS.items():
    router.include_router(build_football_router(_sport, _cfg["league"]))
