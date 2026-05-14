import logging
import subprocess
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from helpers.config import reset_settings
from helpers.process import stop_display, _PROJECT_ROOT

logger = logging.getLogger(__name__)
router = APIRouter()

_WIFI_FLAG = _PROJECT_ROOT / ".wifi_configured"
_NM_HOTSPOT_NAME = "NuggiesHotspot"


def _remove_wifi_connections() -> list[str]:
    """Delete all saved WiFi connections except the setup hotspot. Returns removed names."""
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        logger.warning("nmcli list failed: %s", e)
        return []

    removed = []
    for line in result.stdout.strip().splitlines():
        parts = line.split(":", 1)
        if len(parts) != 2:
            continue
        name, conn_type = parts[0].strip(), parts[1].strip()
        if conn_type == "802-11-wireless" and name != _NM_HOTSPOT_NAME:
            try:
                subprocess.run(
                    ["nmcli", "connection", "delete", name],
                    capture_output=True,
                    timeout=10,
                )
                removed.append(name)
                logger.info("Removed WiFi connection: %s", name)
            except Exception as e:
                logger.warning("Failed to remove connection %s: %s", name, e)

    return removed


@router.post("/factory-reset")
async def factory_reset():
    """Reset all settings to factory defaults. Does not affect WiFi or reboot."""
    logger.info("Factory reset: restoring default settings")
    try:
        stop_display()
    except Exception:
        pass
    reset_settings()
    logger.info("Factory reset complete")
    return JSONResponse({"message": "Settings restored to factory defaults."})


@router.post("/factory-reset-wifi")
async def factory_reset_wifi():
    """Reset settings to defaults, remove all WiFi connections, and reboot.
    The Pi will start the captive portal WiFi setup on next boot."""
    logger.info("Full factory reset: settings + WiFi + reboot")

    try:
        stop_display()
    except Exception:
        pass

    reset_settings()

    removed = _remove_wifi_connections()

    if _WIFI_FLAG.exists():
        _WIFI_FLAG.unlink()
        logger.info("Removed WiFi configured flag")

    logger.info("Rebooting after full factory reset (removed connections: %s)", removed)
    subprocess.Popen(["sudo", "reboot"])

    return JSONResponse(
        {
            "message": "Full factory reset complete. Rebooting now.",
            "wifi_connections_removed": removed,
        }
    )
