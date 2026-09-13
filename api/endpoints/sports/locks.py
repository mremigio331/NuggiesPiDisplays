"""Lock endpoints — pin one or more games to the matrix.

Locks are a list so you can follow several games at once; the display cycles
through only the locked games. Each lock carries the time it was created and
expires 24h later (see _locks.LOCK_TTL).

The server stamps the time, so these are PUT/DELETE endpoints rather than a
settings field the client would have to build timestamps for. Each returns the
full sports settings section, matching PUT /sports/settings.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from helpers.config import read_settings, write_settings

from . import _locks
from .update_settings import VALID_SPORTS

logger = logging.getLogger(__name__)
router = APIRouter()


class LockBody(BaseModel):
    # Which league the game belongs to; defaults to the selected sport
    sport: str | None = None


@router.get("/locks")
async def get_locks():
    """Currently locked games, expired entries excluded."""
    sports = read_settings().get("sports", {})
    return JSONResponse({"locks": _locks.read(sports)})


@router.put("/locks/{event_id}")
async def add_lock(event_id: str, body: LockBody | None = None):
    """Lock a game, or refresh the 24h window if it is already locked."""
    if not _locks.valid_event_id(event_id):
        return JSONResponse(
            {
                "error": f"event_id must be alphanumeric, {_locks.MAX_EVENT_ID} chars max"
            },
            status_code=422,
        )
    settings = read_settings()
    sports = settings.setdefault("sports", {})
    sport = (body.sport if body else None) or sports.get("sport", "")
    if sport and sport not in VALID_SPORTS:
        return JSONResponse(
            {"error": f"sport must be one of {sorted(VALID_SPORTS)}"}, status_code=422
        )

    locks = _locks.write(sports, _locks.add(_locks.read(sports), event_id, sport))
    write_settings(settings)
    logger.info(
        f"Locked game {event_id} ({sport or 'unknown sport'}); {len(locks)} locked"
    )
    return JSONResponse(sports)


@router.delete("/locks/{event_id}")
async def remove_lock(event_id: str):
    """Unlock a single game."""
    settings = read_settings()
    sports = settings.setdefault("sports", {})
    locks = _locks.write(sports, _locks.remove(_locks.read(sports), event_id))
    write_settings(settings)
    logger.info(f"Unlocked game {event_id}; {len(locks)} still locked")
    return JSONResponse(sports)


@router.delete("/locks")
async def clear_locks():
    """Unlock every game."""
    settings = read_settings()
    sports = settings.setdefault("sports", {})
    _locks.write(sports, [])
    write_settings(settings)
    logger.info("Cleared all locked games")
    return JSONResponse(sports)
