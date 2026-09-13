import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

_STATE_FILE = Path("/var/log/nuggies") / "sports_now.json"


@router.get("/now")
async def sports_now():
    """Returns which event_ids the matrix display is currently showing."""
    try:
        return JSONResponse(json.loads(_STATE_FILE.read_text()))
    except Exception:
        return JSONResponse(
            {
                "sport": None,
                "display_mode": None,
                "active_event_ids": [],
                "locked_event_ids": [],
            }
        )
