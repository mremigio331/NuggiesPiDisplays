import logging
from typing import Optional
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import (
    read_display_brightness,
    write_display_brightness,
    BRIGHTNESS_MIN,
    BRIGHTNESS_MAX,
    BRIGHTNESS_PRESETS,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _preset_for(value: int) -> Optional[str]:
    """The preset name whose value exactly matches, else None (custom)."""
    for name, v in BRIGHTNESS_PRESETS.items():
        if v == value:
            return name
    return None


class BrightnessRequest(BaseModel):
    # Send one of these. `preset` ("full"|"medium"|"low") is resolved to its
    # backend-owned value; `brightness` sets a raw 1-100 directly.
    brightness: Optional[int] = None
    preset: Optional[str] = None


def _presets_payload() -> list[dict]:
    return [{"name": n, "value": v} for n, v in BRIGHTNESS_PRESETS.items()]


@router.get("/brightness")
async def get_brightness():
    """Universal LED brightness applied to every display mode, plus the named
    presets the backend owns."""
    value = read_display_brightness()
    return JSONResponse(
        {
            "brightness": value,
            "preset": _preset_for(value),
            "presets": _presets_payload(),
            "min": BRIGHTNESS_MIN,
            "max": BRIGHTNESS_MAX,
        }
    )


@router.put("/brightness")
async def set_brightness(req: BrightnessRequest):
    """Set brightness by preset name or raw value. Takes effect on the next
    display restart."""
    if req.preset is not None:
        name = str(req.preset).strip().lower()
        if name not in BRIGHTNESS_PRESETS:
            return JSONResponse(
                {
                    "error": f"preset must be one of {list(BRIGHTNESS_PRESETS)}, "
                    f"got {req.preset!r}"
                },
                status_code=400,
            )
        target = BRIGHTNESS_PRESETS[name]
    elif req.brightness is not None:
        target = req.brightness
    else:
        return JSONResponse(
            {"error": "provide either 'preset' or 'brightness'"}, status_code=400
        )

    try:
        value = write_display_brightness(target)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    logger.info("Display brightness set to %s (preset=%s)", value, _preset_for(value))
    return JSONResponse({"brightness": value, "preset": _preset_for(value)})
