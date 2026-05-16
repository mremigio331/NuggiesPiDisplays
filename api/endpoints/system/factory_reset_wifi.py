import logging
import subprocess

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from helpers.config import reset_settings
from helpers.process import stop_display
from helpers.wifi_state import WIFI_FLAG, FORCE_PORTAL

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/factory-reset-wifi")
async def factory_reset_wifi():
    """Reset settings, wipe all WiFi connections, and start the captive portal. No reboot."""
    logger.info("Full factory reset: settings + WiFi wipe + captive portal")

    # Non-critical — a stuck display process should not block the reset.
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
            logger.info("Removed .wifi_configured flag")
    except Exception as e:
        logger.warning(f"Could not remove wifi flag (continuing): {e}")

    # List all saved connections — failure here means we cannot safely wipe WiFi.
    try:
        result = subprocess.run(
            ["sudo", "nmcli", "-t", "-f", "UUID,TYPE", "connection", "show"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip() or f"exit code {result.returncode}"
            )
    except Exception as e:
        logger.error(f"Failed to list WiFi connections: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list WiFi connections: {e}"
        )

    removed, failed = [], []
    for line in result.stdout.strip().splitlines():
        parts = line.split(":", 1)
        if len(parts) != 2:
            continue
        uuid, conn_type = parts[0].strip(), parts[1].strip()
        if conn_type != "802-11-wireless":
            continue
        r = subprocess.run(
            ["sudo", "nmcli", "connection", "delete", uuid],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            removed.append(uuid)
            logger.info(f"Deleted WiFi connection: {uuid}")
        else:
            failed.append(uuid)
            logger.warning(f"Failed to delete {uuid}: {r.stderr.strip()}")

    logger.info(f"WiFi connections removed: {removed}, failed: {failed}")

    # Non-critical — NM will reconcile the disconnected state on its own.
    try:
        subprocess.run(
            ["sudo", "nmcli", "device", "disconnect", "wlan0"],
            capture_output=True,
            timeout=10,
        )
        logger.info("Disconnected wlan0")
    except Exception as e:
        logger.warning(f"wlan0 disconnect failed (continuing): {e}")

    # Non-critical — rule may not exist if this is the first reset.
    try:
        subprocess.run(
            [
                "sudo",
                "iptables",
                "-t",
                "nat",
                "-D",
                "PREROUTING",
                "-p",
                "tcp",
                "--dport",
                "80",
                "-j",
                "REDIRECT",
                "--to-port",
                "8000",
            ],
            capture_output=True,
            timeout=5,
        )
        logger.info("Removed port-80 → 8000 iptables redirect")
    except Exception as e:
        logger.warning(f"iptables rule removal failed (continuing): {e}")

    # Critical — the boot service reads this marker to skip the NM connectivity check.
    try:
        FORCE_PORTAL.touch()
        logger.info("Wrote .force_portal marker")
    except Exception as e:
        logger.error(f"Failed to write .force_portal marker: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to write portal marker: {e}"
        )

    # Critical — without this the captive portal will not start.
    try:
        subprocess.Popen(["sudo", "systemctl", "restart", "nuggies-wifi-setup"])
        logger.info(
            "nuggies-wifi-setup restart triggered — captive portal starting in background"
        )
    except Exception as e:
        logger.error(f"Failed to restart wifi-setup service: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start captive portal service: {e}"
        )

    response = {
        "message": "Factory reset complete. Connect to NuggiesSetup WiFi to reconfigure."
    }
    if failed:
        response["warning"] = (
            f"Could not delete {len(failed)} WiFi connection(s): {failed}"
        )

    return JSONResponse(response)
