from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from endpoints.stonks._now_state import _current

router = APIRouter()


class NowBody(BaseModel):
    symbol: str
    cycle_key: str


@router.put("/now")
async def set_now(body: NowBody):
    _current["symbol"] = body.symbol
    _current["cycle_key"] = body.cycle_key
    return JSONResponse(_current)
