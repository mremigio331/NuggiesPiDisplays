import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from helpers.dev_config import is_dev_mode
from helpers.process import _PROJECT_ROOT
from helpers.wifi_state import FORCE_PORTAL, WIFI_FLAG

logger = logging.getLogger(__name__)
router = APIRouter()

_FACTORY_WIFI_RESET = _PROJECT_ROOT / ".factory_wifi_reset"


@router.post("/forget-wifi")
async def forget_wifi():
    """Dev-mode only: mark WiFi for wipe on next boot and clear the wifi flag."""
    if not is_dev_mode():
        raise HTTPException(status_code=403, detail="Only available in dev mode.")

    if WIFI_FLAG.exists():
        WIFI_FLAG.unlink()
    _FACTORY_WIFI_RESET.touch()
    # Additive: also force the portal so a reset device reaches the setup page even if a
    # stale association survives. Does not change the .factory_wifi_reset write above.
    FORCE_PORTAL.touch()
    logger.info("Wrote .factory_wifi_reset and .force_portal markers")

    return JSONResponse(
        {
            "message": "WiFi will be cleared on next reboot. Use Restart Pi to re-run setup."
        }
    )
