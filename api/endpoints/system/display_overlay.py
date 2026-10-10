import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from helpers.config import read_overlay, write_overlay

logger = logging.getLogger(__name__)
router = APIRouter()

# Overlay kinds the display knows how to render. Keep in sync with the display
# overlay helper (display/common/overlay.py).
_VALID_KINDS = {"reset_prompt", "reset_running"}


class OverlayRequest(BaseModel):
    # None clears the overlay (resume normal rendering).
    kind: str | None = None
    seconds_left: int | None = None


@router.get("/display-overlay")
async def get_display_overlay():
    """Return the current display overlay (or null)."""
    return JSONResponse({"overlay": read_overlay()})


@router.post("/display-overlay")
async def set_display_overlay(req: OverlayRequest):
    """Set or clear the full-screen display overlay.

    The display polls settings ~1x/second and renders this over its normal
    content, so this is how the API 'flushes' the screen and shows the
    factory-reset messaging. Passing kind=null clears it.
    """
    if req.kind is None:
        write_overlay(None)
        return JSONResponse({"overlay": None})

    if req.kind not in _VALID_KINDS:
        return JSONResponse(
            {"error": f"unknown overlay kind: {req.kind}"}, status_code=400
        )

    overlay: dict = {"kind": req.kind}
    if req.seconds_left is not None:
        overlay["seconds_left"] = max(0, int(req.seconds_left))
    write_overlay(overlay)
    logger.info(f"Display overlay set: {overlay}")
    return JSONResponse({"overlay": overlay})
