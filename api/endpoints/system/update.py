import logging
import subprocess
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/update")
async def system_update(websocket: WebSocket):
    await websocket.accept()
    logger.info("System update websocket opened")
    try:
        process = subprocess.Popen(
            "sudo apt update && sudo apt upgrade -y",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=True,
        )
        for line in iter(process.stdout.readline, ""):
            await websocket.send_text(line.rstrip())
        process.stdout.close()
        process.wait()
        await websocket.close()
    except WebSocketDisconnect:
        logger.info("System update websocket closed by client")
    except Exception as e:
        logger.exception("System update error")
        await websocket.send_text(f"Error: {e}")
        await websocket.close()
