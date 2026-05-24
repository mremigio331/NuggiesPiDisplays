import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.update_check import refresh

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/check-update")
async def check_update():
    """Force a fresh git fetch and return the result."""
    status = await refresh()
    if status.error:
        return JSONResponse({"error": status.error}, status_code=503)
    return JSONResponse(status.to_dict())
