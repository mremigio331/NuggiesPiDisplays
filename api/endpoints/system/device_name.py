import asyncio
import logging
import socket
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from helpers.system import _privileged_command

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.append(str(_PROJECT_ROOT))

from wifi_setup.device_name import normalize_name  # noqa: E402

logger = logging.getLogger(__name__)
router = APIRouter()

# Root-only rename helper. setup.sh grants exactly this script with `--set *`
# in sudoers; the script re-validates the name before touching the system.
_RENAME_SCRIPT = _PROJECT_ROOT / "wifi_setup" / "device_name.py"


class DeviceNameRequest(BaseModel):
    name: str


def _current() -> dict:
    hostname = socket.gethostname()
    return {"hostname": hostname, "mdns_name": f"{hostname}.local"}


@router.get("/device-name")
async def get_device_name():
    """This device's name, which is also its <name>.local address."""
    return JSONResponse(_current())


@router.put("/device-name")
async def set_device_name(req: DeviceNameRequest):
    """Rename the device. The new <name>.local works as soon as this returns.

    Validation happens here AND in the root helper. A failed rename leaves the
    old name in place (the helper never raises), so the device stays reachable.
    """
    name = normalize_name(req.name)
    if name is None:
        return JSONResponse(
            {
                "error": "Use letters, numbers and dashes only (1-63 characters, "
                "no dash at the start or end)."
            },
            status_code=400,
        )
    if name == socket.gethostname():
        return JSONResponse({**_current(), "changed": False})

    cmd = _privileged_command("python3", str(_RENAME_SCRIPT), "--set", name)

    def _run():
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    try:
        result = await asyncio.get_running_loop().run_in_executor(None, _run)
    except Exception as e:  # noqa: BLE001
        logger.error("Device rename to %s failed to run: %r", name, e)
        return JSONResponse({"error": "Rename failed to run."}, status_code=500)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        logger.error("Device rename to %s failed: %s", name, err)
        return JSONResponse(
            {"error": "Rename failed. The device kept its old name."},
            status_code=500,
        )
    logger.info("Device renamed to %s", name)
    return JSONResponse({**_current(), "changed": True})
