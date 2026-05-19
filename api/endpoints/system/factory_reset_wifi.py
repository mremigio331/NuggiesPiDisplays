import logging
import subprocess

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from helpers.config import reset_settings
from helpers.process import _PROJECT_ROOT, stop_display
from helpers.wifi_state import WIFI_FLAG

logger = logging.getLogger(__name__)
router = APIRouter()

_FACTORY_WIFI_RESET = _PROJECT_ROOT / ".factory_wifi_reset"


@router.post("/factory-reset-wifi")
async def factory_reset_wifi():
    """Reset settings, mark WiFi for wipe on next boot, then reboot."""
    logger.info("Full factory reset: settings + WiFi wipe marker + reboot")

    try:
        stop_display()
        logger.info("Display stopped")
    except Exception as e:
        logger.warning(f"Could not stop display (continuing): {e}")

    try:
        reset_settings()
        logger.info("Settings reset to defaults")
    except Exception as e:
        logger.error(f"Failed to reset settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset settings: {e}")

    try:
        if WIFI_FLAG.exists():
            WIFI_FLAG.unlink()
        _FACTORY_WIFI_RESET.touch()
        logger.info("Wrote .factory_wifi_reset marker")
    except Exception as e:
        logger.error(f"Failed to write reset marker: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to write reset marker: {e}"
        )

    logger.info("Rebooting for factory WiFi reset")
    result = subprocess.run(["sudo", "reboot"], capture_output=True)
    if result.returncode != 0:
        err = result.stderr.decode().strip()
        logger.error(f"Reboot failed: {err}")
        raise HTTPException(status_code=500, detail=f"Reboot failed: {err}")

    return JSONResponse(
        {
            "message": "Factory reset complete. Pi is rebooting — connect to NuggiesSetup WiFi to reconfigure."
        }
    )
