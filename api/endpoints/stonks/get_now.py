from fastapi import APIRouter
from fastapi.responses import JSONResponse

from endpoints.stonks._now_state import _current

router = APIRouter()


@router.get("/now")
async def get_now():
    return JSONResponse(_current)
