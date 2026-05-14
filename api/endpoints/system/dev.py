import logging
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from helpers.dev_config import is_dev_mode
from helpers.process import _PROJECT_ROOT

logger = logging.getLogger(__name__)
router = APIRouter()

_WIFI_FLAG = _PROJECT_ROOT / ".wifi_configured"
_NM_HOTSPOT_NAME = "NuggiesHotspot"


@router.get("/dev-mode")
async def get_dev_mode():
    return JSONResponse({"dev_mode": is_dev_mode()})


@router.post("/forget-wifi")
async def forget_wifi():
    """Dev-mode only: remove all saved WiFi connections and the wifi flag.
    The display and settings are untouched. Reboot separately to trigger setup."""
    if not is_dev_mode():
        raise HTTPException(status_code=403, detail="Only available in dev mode.")

    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"nmcli failed: {e}")

    removed = []
    for line in result.stdout.strip().splitlines():
        parts = line.split(":", 1)
        if len(parts) != 2:
            continue
        name, conn_type = parts[0].strip(), parts[1].strip()
        if conn_type == "802-11-wireless" and name != _NM_HOTSPOT_NAME:
            subprocess.run(
                ["nmcli", "connection", "delete", name],
                capture_output=True,
                timeout=10,
            )
            removed.append(name)
            logger.info("Removed WiFi connection: %s", name)

    if _WIFI_FLAG.exists():
        _WIFI_FLAG.unlink()
        logger.info("Removed .wifi_configured flag")

    logger.info("forget-wifi complete, removed: %s", removed)
    return JSONResponse(
        {
            "message": "WiFi connections cleared. Restart the Pi to re-run setup.",
            "removed": removed,
        }
    )
