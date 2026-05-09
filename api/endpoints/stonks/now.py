from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

_current: dict = {"symbol": None, "cycle_key": None}


@router.get("/now")
async def get_now():
    return JSONResponse(_current)


class NowBody(BaseModel):
    symbol: str
    cycle_key: str


@router.put("/now")
async def set_now(body: NowBody):
    _current["symbol"] = body.symbol
    _current["cycle_key"] = body.cycle_key
    return JSONResponse(_current)
