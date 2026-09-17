import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from helpers.system import SystemManager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/force-wifi-portal")
async def force_wifi_portal():
    """Force the WiFi setup portal (AP) to come up, even while reporting connected.

    Writes the FORCE_PORTAL marker the boot service honours, clears the
    ``.wifi_configured`` cache through the shared resolver, then restarts
    ``nuggies-wifi-setup.service`` detached so this response flushes before the WiFi
    association drops. The ``NuggiesDisplay`` AP should appear within ~30s.
    """
    try:
        SystemManager().force_wifi_portal()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return JSONResponse(
        {
            "message": (
                "Force-portal marker written and WiFi setup service restart issued. "
                "The device will drop its WiFi association and the NuggiesDisplay setup "
                "AP should appear within ~30 seconds."
            ),
            "marker_written": ".force_portal",
            "flag_cleared": ".wifi_configured",
            "restart_issued": "systemctl restart nuggies-wifi-setup.service",
            "confirm_via": "GET /api/wifi/status (while the API is still reachable)",
        }
    )
