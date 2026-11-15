import logging
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from helpers.timers import (
    TIMER_MAX_COUNT,
    TIMER_MAX_LABEL,
    TIMER_MAX_SECONDS,
    TIMER_SNOOZE_SECONDS,
    add_timer,
    clean_label,
    delete_timer,
    dismiss_done,
    list_timers,
    next_clock_time,
    snooze_timer,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class TimerBody(BaseModel):
    label: str = ""
    # Exactly one of these: "at" is a 24-hour device clock time ("16:00", the
    # next time the clock reads it); "seconds" counts down from now.
    at: str | None = None
    seconds: int | None = None


class SnoozeBody(BaseModel):
    seconds: int = TIMER_SNOOZE_SECONDS


def _payload() -> dict:
    """Saved timers plus the limits the website shows. ``now`` lets the website
    count down against the device clock instead of the phone's."""
    return {
        "now": int(time.time()),
        "timers": list_timers(),
        "max_count": TIMER_MAX_COUNT,
        "max_label": TIMER_MAX_LABEL,
        "max_seconds": TIMER_MAX_SECONDS,
        "snooze_seconds": TIMER_SNOOZE_SECONDS,
    }


@router.get("")
async def get_timers():
    return JSONResponse(_payload())


@router.post("")
async def create_timer(body: TimerBody):
    if (body.at is None) == (body.seconds is None):
        raise HTTPException(status_code=422, detail="Set a clock time or a length, not both")
    if len(body.label.strip()) > TIMER_MAX_LABEL:
        raise HTTPException(
            status_code=422, detail=f"Label must be {TIMER_MAX_LABEL} characters or less"
        )

    if body.seconds is not None:
        if not (1 <= body.seconds <= TIMER_MAX_SECONDS):
            raise HTTPException(status_code=422, detail="Length must be 1 second to 24 hours")
        ends_at = int(time.time()) + body.seconds
    else:
        try:
            ends_at = next_clock_time(body.at)
        except ValueError:
            raise HTTPException(status_code=422, detail="Time must be HH:MM (24-hour)")

    try:
        add_timer(clean_label(body.label), ends_at)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return JSONResponse(_payload())


@router.post("/dismiss-done")
async def dismiss_done_timers():
    dismiss_done()
    return JSONResponse(_payload())


@router.post("/{timer_id}/snooze")
async def snooze(timer_id: str, body: SnoozeBody | None = None):
    seconds = (body or SnoozeBody()).seconds
    if not (1 <= seconds <= TIMER_MAX_SECONDS):
        raise HTTPException(status_code=422, detail="Snooze must be 1 second to 24 hours")
    if not snooze_timer(timer_id, seconds):
        raise HTTPException(status_code=404, detail="Timer not found")
    return JSONResponse(_payload())


@router.delete("/{timer_id}")
async def remove_timer(timer_id: str):
    # Cancel before it ends, or dismiss once done. Either way the entry is gone.
    if not delete_timer(timer_id):
        raise HTTPException(status_code=404, detail="Timer not found")
    return JSONResponse(_payload())
