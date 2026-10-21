"""Aggregated favourites feed — two games per favourited team.

The "favorites" pseudo-sport is not a real ESPN league: it is a per-team view
built from the schedule of every favourited team, across whichever leagues the
user has favourites in. For each favourited team the feed emits, in order:

    1. the team's LAST completed game (final score), and
    2. the team's CURRENT game if one is live, otherwise its NEXT upcoming game.

So each team contributes last+live or last+next — never all three. The two
games for a team are kept adjacent so the display's overview mode can show a
team's pair side by side.

Because ESPN team ids are only unique within a league (see _favorites.py), each
team's schedule is fetched from its own league, and every emitted game is tagged
with:
  * ``sport``        — the originating league, so the display routes rendering;
  * ``favorite_id``  — the favourited team id this game belongs to, so the
                       display can group a team's two games together;
  * ``slot``         — "last" | "live" | "next", what role this game plays.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from helpers.config import read_settings
from helpers.espn_client import ESPNClient

from . import _favorites

logger = logging.getLogger(__name__)
router = APIRouter()

# Dedicated client (not common._client) so the longer schedule payloads are
# cached independently of the 15s live-scoreboard cache. Team schedules change
# at most a few times a day, so a longer TTL avoids hammering ESPN.
_client = ESPNClient(cache_ttl=300)


def _is_favorite_team(game: dict, favorite_id: str) -> bool:
    """True when this favourited team is either side of the game.

    Match on team id (what favourites are stored as) and fall back to the
    abbreviation so legacy abbreviation-based picks keep working.
    """
    fid = str(favorite_id).upper()
    keys = {
        str(game.get("home_id") or "").upper(),
        str(game.get("away_id") or "").upper(),
        str(game.get("home_team") or "").upper(),
        str(game.get("away_team") or "").upper(),
    }
    keys.discard("")
    return fid in keys


def _pick_last_and_next(schedule: list[dict]) -> list[dict]:
    """From one team's (oldest-first) schedule, pick last + live-or-next.

    Returns 0–2 games tagged with their ``slot``:
      * "last" — the most recent completed (state == "post") game;
      * "live" — an in-progress game if the team has one right now; otherwise
      * "next" — the earliest upcoming (state == "pre") game.

    A team with no completed games (season hasn't started) yields just the
    upcoming/live game; a team whose season is over yields just the last game.
    """
    last_game = None
    live_game = None
    next_game = None

    for game in schedule:
        state = game.get("state", "pre")
        if state == "post":
            # Schedule is oldest-first, so the last "post" seen is the most
            # recent completed game.
            last_game = game
        elif state == "in" and live_game is None:
            live_game = game
        elif state == "pre" and next_game is None:
            next_game = game

    picks: list[dict] = []
    if last_game is not None:
        picks.append({**last_game, "slot": "last"})
    upcoming = live_game or next_game
    if upcoming is not None:
        picks.append({**upcoming, "slot": "live" if live_game else "next"})
    return picks


def _attach_records(game: dict, sport: str) -> None:
    """Enrich an UPCOMING game in place with records and season leaders.

    Only upcoming (pre) games are enriched: a final already shows the result and
    a live game shows the score. Adds:
      * ``away_record`` / ``home_record`` — overall win-loss records (the
        schedule's upcoming games carry none), from ESPN's teams endpoint;
      * ``leaders`` — ``{"home": [...], "away": [...]}`` stat leaders from the
        game summary (ESPN gives SEASON leaders even before the game), each a
        ``{category, label, name, value}`` dict.
    Both are memoised/cached in the client, so repeated favourites polls don't
    refetch. A failed lookup leaves the field empty and the renderer omits it.
    """
    if game.get("state", "pre") != "pre":
        return
    home_id = str(game.get("home_id") or "")
    away_id = str(game.get("away_id") or "")
    if home_id:
        game["home_record"] = _client.get_team_record(sport, home_id)
    if away_id:
        game["away_record"] = _client.get_team_record(sport, away_id)
    event_id = str(game.get("event_id") or "")
    if event_id:
        game["leaders"] = _client.get_summary_leaders(sport, event_id)


def collect_favorite_team_games(favorites: dict[str, list[str]]) -> list[dict]:
    """Per favourited team: its last game + its live-or-next game, grouped.

    ``favorites`` is the normalised {sport: [team_id, …]} map. For each team the
    team's schedule is fetched from its league and reduced to last + live/next
    by :func:`_pick_last_and_next`. Each game is tagged with its ``sport``,
    ``favorite_id`` and ``slot``. A team's games stay adjacent in the returned
    list so the display can render a team's pair together. One slow or failing
    team never sinks the whole feed.
    """
    games: list[dict] = []
    for sport, team_ids in favorites.items():
        if not team_ids:
            continue
        for team_id in team_ids:
            try:
                schedule = _client.get_team_schedule(sport, str(team_id))
            except Exception as e:
                logger.error(
                    f"Favourites: {sport} team {team_id} schedule fetch failed: {e}"
                )
                continue
            # Keep only games actually involving this team (defensive — a
            # team's own schedule should always, but tagging stays correct).
            mine = [g for g in schedule if _is_favorite_team(g, team_id)]
            for game in _pick_last_and_next(mine):
                tagged = {**game, "sport": sport, "favorite_id": str(team_id).upper()}
                _attach_records(tagged, sport)
                games.append(tagged)
    return games


@router.get("/favorites/scoreboard")
async def favorites_scoreboard():
    """Two games per favourited team: last + current/next, grouped by team.

    Each game carries ``sport`` (its league), ``favorite_id`` (the team it was
    picked for) and ``slot`` ("last" | "live" | "next"). Games are ordered by
    team so a team's pair is adjacent — the display groups and renders them
    together in overview mode.
    """
    sports = read_settings().get("sports", {})
    favorites = _favorites.read_all(sports)
    games = collect_favorite_team_games(favorites)
    return JSONResponse({"sport": "favorites", "games": games})
