"""Aggregated favourites scoreboard — one feed across every league.

The "favorites" pseudo-sport is not a real ESPN league: it is the union of
every game involving a favourited team, drawn from whichever leagues the user
has favourites in. Because ESPN team ids are only unique within a league (see
_favorites.py), each league is fetched separately and filtered against its own
favourites list, then every surviving game is tagged with the sport it came
from so the display knows which renderer and detail endpoint to use.

This is what makes the favourites display "self aware": a plain scoreboard game
dict carries no league, so without the `sport` tag added here a merged feed
could not be rendered correctly.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from helpers.config import read_settings

from . import _favorites
from .common import scoreboard_for_sport, sort_games

logger = logging.getLogger(__name__)
router = APIRouter()


def _game_has_favorite(game: dict, favorite_ids: set[str]) -> bool:
    """True when either side of the game is a favourited team.

    Match on team id (what favourites are stored as) and fall back to the
    abbreviation so legacy abbreviation-based picks keep working — mirrors the
    web UI's isFavoriteGame().
    """
    keys = {
        str(game.get("home_id") or ""),
        str(game.get("away_id") or ""),
        str(game.get("home_team") or "").upper(),
        str(game.get("away_team") or "").upper(),
    }
    keys.discard("")
    return bool(keys & favorite_ids)


def collect_favorite_games(favorites: dict[str, list[str]]) -> list[dict]:
    """Games involving a favourited team across every league, sport-tagged.

    `favorites` is the normalised {sport: [team_id, …]} map. For each sport with
    at least one favourite, fetch that league's scoreboard, keep games that
    involve a favourite, and stamp each kept game with its sport so a mixed feed
    stays renderable. One slow or failing league never sinks the whole feed.
    """
    games: list[dict] = []
    for sport, team_ids in favorites.items():
        if not team_ids:
            continue
        favorite_ids = {str(t).upper() for t in team_ids}
        try:
            league_games = scoreboard_for_sport(sport)
        except Exception as e:
            logger.error(f"Favourites: {sport} scoreboard fetch failed: {e}")
            continue
        for game in league_games:
            if _game_has_favorite(game, favorite_ids):
                # Tag with the originating league — the only place a game dict
                # gains a sport, which the display routes rendering by.
                games.append({**game, "sport": sport})
    return games


@router.get("/favorites/scoreboard")
async def favorites_scoreboard():
    """Every current game involving a favourited team, across all leagues.

    Each game carries a `sport` key naming its league. Games are ordered live
    first, then final, then scheduled (same rule as single-league scoreboards).
    """
    sports = read_settings().get("sports", {})
    favorites = _favorites.read_all(sports)
    games = sort_games(collect_favorite_games(favorites))
    return JSONResponse({"sport": "favorites", "games": games})
