from collections.abc import Callable
from fastapi import HTTPException
from helpers.espn_client import ESPNClient

_client = ESPNClient(cache_ttl=15)

_STATE_ORDER = {"in": 0, "post": 1, "pre": 2}


def scoreboard_for_sport(sport: str) -> list[dict]:
    """Raw (unsorted) scoreboard games for any single league/sport key.

    Central dispatch from a sport key to the right ESPN client call — football
    and soccer leagues pass their league slug, the rest map one-to-one. Returns
    [] for an unknown sport. Used by the favourites aggregator so every league
    is reachable from one place.

    FOOTBALL_SPORTS / SOCCER_SPORTS are imported lazily: football.py and
    soccer.py import from this module, so a top-level import here would be a
    cycle.
    """
    from .football import FOOTBALL_SPORTS
    from .soccer import SOCCER_SPORTS

    if sport in FOOTBALL_SPORTS:
        return _client.get_football_scoreboard(FOOTBALL_SPORTS[sport]["league"])
    if sport in SOCCER_SPORTS:
        return _client.get_soccer_scoreboard(SOCCER_SPORTS[sport]["league"])
    simple = {
        "nba": _client.get_nba_scoreboard,
        "wnba": _client.get_wnba_scoreboard,
        "mlb": _client.get_mlb_scoreboard,
        "nhl": _client.get_nhl_scoreboard,
    }
    fetch = simple.get(sport)
    return fetch() if fetch else []


def sort_games(games: list[dict]) -> list[dict]:
    """Live games first (latest period first), then final, then scheduled."""
    return sorted(
        games,
        key=lambda g: (
            _STATE_ORDER.get(g.get("state", "pre"), 2),
            -(g.get("period") or 0),
        ),
    )


def game_details_or_404(fetcher: Callable[[str], dict | None], event_id: str) -> dict:
    details = fetcher(event_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Game details not available")
    return details
