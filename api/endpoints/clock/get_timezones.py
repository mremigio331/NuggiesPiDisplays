import logging
from zoneinfo import available_timezones
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

_TIMEZONES = sorted(available_timezones())
PAGE_SIZE = 50


@router.get("/timezones")
async def get_timezones(
    page: int = Query(1, ge=1), search: str = Query("", max_length=100)
):
    filtered = (
        [tz for tz in _TIMEZONES if search.lower() in tz.lower()]
        if search
        else _TIMEZONES
    )
    total = len(filtered)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    return JSONResponse(
        {
            "timezones": filtered[start:end],
            "page": page,
            "total_pages": total_pages,
            "total": total,
        }
    )
