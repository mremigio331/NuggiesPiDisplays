import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import (
    TEXT_ALIGNS,
    TEXT_COLOR_MODES,
    TEXT_MAX_LENGTH,
    TEXT_MAX_ROWS,
    TEXT_MAX_SCROLL_SECONDS,
    TEXT_MIN_SCROLL_SECONDS,
    normalize_text,
    read_settings,
    text_char_allowed,
    write_settings,
)
from .ws_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


class TextRow(BaseModel):
    text: str = ""
    color: List[int] = [255, 255, 255]
    # "solid" uses `color`; "rainbow" (aka Caitlin Mode) slides a rainbow right.
    color_mode: str = "solid"
    align: str = "center"
    # Scroll when too wide for the board; False cuts the text off instead.
    scroll: bool = True


class TextSettings(BaseModel):
    # How many rows are on the board (1-5). Fewer rows use a bigger font.
    row_count: Optional[int] = None
    # Seconds for a row to scroll one letter (1-5).
    scroll_seconds: Optional[int] = None
    # Always all five rows, so lowering row_count doesn't lose the hidden text.
    rows: Optional[List[TextRow]] = None


def _validate_row(row: TextRow, number: int) -> None:
    if len(row.text) > TEXT_MAX_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Row {number} is longer than {TEXT_MAX_LENGTH} characters",
        )
    if not all(text_char_allowed(ch) for ch in row.text):
        raise HTTPException(
            status_code=422,
            detail=f"Row {number} has characters the display can't show",
        )
    if len(row.color) != 3 or not all(0 <= v <= 255 for v in row.color):
        raise HTTPException(
            status_code=422, detail="color must be [r, g, b] with values 0-255"
        )
    if row.color_mode not in TEXT_COLOR_MODES:
        raise HTTPException(
            status_code=422, detail="color_mode must be 'solid' or 'rainbow'"
        )
    if row.align not in TEXT_ALIGNS:
        raise HTTPException(
            status_code=422, detail="align must be 'left', 'center' or 'right'"
        )


@router.put("/settings")
async def update_settings(body: TextSettings):
    updates = body.model_dump(exclude_none=True)

    if "row_count" in updates and not (1 <= updates["row_count"] <= TEXT_MAX_ROWS):
        raise HTTPException(
            status_code=422, detail=f"row_count must be between 1 and {TEXT_MAX_ROWS}"
        )

    if "scroll_seconds" in updates and not (
        TEXT_MIN_SCROLL_SECONDS <= updates["scroll_seconds"] <= TEXT_MAX_SCROLL_SECONDS
    ):
        raise HTTPException(
            status_code=422,
            detail=f"scroll_seconds must be between {TEXT_MIN_SCROLL_SECONDS} and {TEXT_MAX_SCROLL_SECONDS}",
        )

    if body.rows is not None:
        if len(body.rows) != TEXT_MAX_ROWS:
            raise HTTPException(
                status_code=422, detail=f"rows must have {TEXT_MAX_ROWS} entries"
            )
        for number, row in enumerate(body.rows, start=1):
            _validate_row(row, number)

    settings = read_settings()
    text = normalize_text({**normalize_text(settings.get("text")), **updates})
    settings["text"] = text
    write_settings(settings)
    logger.info(f"Text settings updated: {list(updates.keys())}")

    await manager.broadcast(text)
    return JSONResponse(text)
