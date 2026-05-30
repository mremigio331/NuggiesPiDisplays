from collections.abc import Callable
from fastapi import HTTPException
from helpers.espn_client import ESPNClient

_client = ESPNClient(cache_ttl=15)

_STATE_ORDER = {"in": 0, "post": 1, "pre": 2}


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
