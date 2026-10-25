import logging
import subprocess
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SETUP_SH = _PROJECT_ROOT / "setup.sh"

# Map a component name to its scoped setup.sh flag. None/"all" => full --update.
_COMPONENT_FLAG = {
    "api": "--update-api",
    "display": "--update-display",
    "website": "--update-website",
    "system": "--update-system",
}


@router.websocket("/update")
async def system_update(websocket: WebSocket):
    await websocket.accept()
    # Scope the update to one component (?component=api) and/or force a full
    # reinstall bypassing the skip-if-unchanged checks (?force=true). No
    # component (or component=all) runs the classic full --update.
    component = (websocket.query_params.get("component") or "").strip().lower()
    force = (websocket.query_params.get("force") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    flag = "--update"
    if component and component != "all":
        flag = _COMPONENT_FLAG.get(component)
        if flag is None:
            await websocket.send_text(
                f"Error: unknown component '{component}'. "
                f"Valid: {', '.join(_COMPONENT_FLAG)} or 'all'."
            )
            await websocket.close()
            return

    cmd = ["sudo", "-n", "bash", str(_SETUP_SH), flag]
    if force:
        cmd.append("--force")
    logger.info(
        "System update started (component=%s force=%s): %s",
        component or "all",
        force,
        flag,
    )
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(_PROJECT_ROOT),
        )
        for line in iter(process.stdout.readline, ""):
            await websocket.send_text(line.rstrip())
        process.stdout.close()
        process.wait()
        await websocket.send_text(f"--- Exit code: {process.returncode}")
        await websocket.close()
    except WebSocketDisconnect:
        logger.info("System update websocket closed by client")
    except Exception as e:
        logger.exception("System update error")
        await websocket.send_text(f"Error: {e}")
        await websocket.close()
