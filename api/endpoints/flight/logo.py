import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from helpers.airline_logos import SIZES, get_logo, valid_code

logger = logging.getLogger(__name__)
router = APIRouter()


# Plain `def`: the first request for a logo downloads it.
@router.get("/logo/{code}.png")
def logo(code: str, size: int = 64):
    """Airline logo by IATA code (DL, AS). size is 16 (panel), 32 or 64."""
    code = code.upper()
    if not valid_code(code) or size not in SIZES:
        raise HTTPException(status_code=422, detail="code must be 2 letters/digits")
    data = get_logo(code, size)
    if data is None:
        raise HTTPException(status_code=404, detail="no logo for this airline")
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )
