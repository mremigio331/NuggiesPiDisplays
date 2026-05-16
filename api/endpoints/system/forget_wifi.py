import logging
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from helpers.ap_config import AP_CON_NAME as _NM_HOTSPOT_NAME
from helpers.dev_config import is_dev_mode
from helpers.wifi_state import WIFI_FLAG

logger = logging.getLogger(__name__)
router = APIRouter()

_NETPLAN_DIR = Path("/etc/netplan")


@router.post("/forget-wifi")
async def forget_wifi():
    """Dev-mode only: remove all saved WiFi connections and the wifi flag."""
    if not is_dev_mode():
        raise HTTPException(status_code=403, detail="Only available in dev mode.")

    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,UUID,TYPE", "connection", "show"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"nmcli failed: {e}")

    removed = []
    for line in result.stdout.strip().splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        name, uuid, conn_type = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if conn_type != "802-11-wireless" or name == _NM_HOTSPOT_NAME:
            continue

        subprocess.run(
            ["nmcli", "connection", "delete", name],
            capture_output=True,
            timeout=10,
        )
        removed.append(name)
        logger.info(f"Removed WiFi connection: {name}")

        netplan_file = _NETPLAN_DIR / f"90-NM-{uuid}.yaml"
        if netplan_file.exists():
            try:
                netplan_file.unlink()
                logger.info(f"Removed netplan file: {netplan_file}")
            except Exception as e:
                logger.warning(f"Failed to remove netplan file {netplan_file}: {e}")

    if WIFI_FLAG.exists():
        WIFI_FLAG.unlink()
        logger.info("Removed .wifi_configured flag")

    logger.info(f"forget-wifi complete, removed: {removed}")
    return JSONResponse(
        {
            "message": "WiFi connections cleared. Restart the Pi to re-run setup.",
            "removed": removed,
        }
    )
