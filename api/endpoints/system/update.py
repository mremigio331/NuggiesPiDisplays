import logging
import subprocess
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SETUP_SH = _PROJECT_ROOT / "setup.sh"


@router.websocket("/update")
async def system_update(websocket: WebSocket):
    await websocket.accept()
    logger.info("System update started")
    try:
        cmd = ["sudo", "-n", "bash", str(_SETUP_SH), "--update"]
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
