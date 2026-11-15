import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from helpers.health import KEEP_SAMPLES, SAMPLE_SECONDS, read_history, snapshot

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def get_health(hours: float = Query(24, gt=0, le=24 * 7)):
    """Live device stats plus the logged history for the last ``hours``."""
    return JSONResponse(
        {
            "current": await snapshot(),
            "history": read_history(hours),
            "sample_seconds": SAMPLE_SECONDS,
            "keep_hours": KEEP_SAMPLES * SAMPLE_SECONDS // 3600,
        }
    )
