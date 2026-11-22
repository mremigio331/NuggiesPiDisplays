import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.flights import get_nearby

logger = logging.getLogger(__name__)
router = APIRouter()


# Plain `def` (not async): the upstream call blocks, so FastAPI runs this in
# its thread pool and the event loop stays free for other requests.
@router.get("/nearby")
def nearby():
    """Planes in the air around the saved spot, nearest first.

    The panel and the website both read this. The upstream feeds are called
    at most once a minute; every other call gets the cached answer.
    """
    body, status = get_nearby()
    return JSONResponse(body, status_code=status)
