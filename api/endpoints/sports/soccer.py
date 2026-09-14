"""Soccer scoreboard routes — one sport per soccer league.

Every ESPN soccer league shares the same endpoints and payload shape, so the
routes are built from a single factory. Each league is its own sport: NWSL lives
at `/sports/nwsl/*`, and another league would live at `/sports/<key>/*`.

Adding a soccer league is one entry in SOCCER_SPORTS below — routes, settings
validation (see update_settings.py), the teams picker (see espn_client.py) and
the display registry all read from it.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .common import _client, game_details_or_404, sort_games

# sport key → {league: ESPN league slug, name: human label}
SOCCER_SPORTS: dict[str, dict[str, str]] = {
    "nwsl": {"league": "usa.nwsl", "name": "NWSL"},
    # Add more leagues here, e.g.:
    # "epl": {"league": "eng.1", "name": "Premier League"},
    # "wwc": {"league": "fifa.wwc", "name": "Women's World Cup"},
}


def build_soccer_router(sport: str, league: str) -> APIRouter:
    """Return scoreboard + game-details routes for one soccer league."""
    league_router = APIRouter()

    @league_router.get(f"/{sport}/scoreboard", name=f"{sport}_scoreboard")
    async def soccer_scoreboard():
        games = sort_games(_client.get_soccer_scoreboard(league))
        return JSONResponse({"sport": sport, "league": league, "games": games})

    @league_router.get(f"/{sport}/game/{{event_id}}", name=f"{sport}_game_details")
    async def soccer_game_details(event_id: str):
        details = game_details_or_404(
            lambda eid: _client.get_soccer_game_details(eid, league), event_id
        )
        return JSONResponse(details)

    return league_router


router = APIRouter()


@router.get("/soccer/leagues")
async def soccer_leagues():
    """Return the soccer leagues available as sports."""
    return JSONResponse(
        {
            "leagues": [
                {"key": key, "name": cfg["name"]}
                for key, cfg in SOCCER_SPORTS.items()
            ]
        }
    )


for _sport, _cfg in SOCCER_SPORTS.items():
    router.include_router(build_soccer_router(_sport, _cfg["league"]))
