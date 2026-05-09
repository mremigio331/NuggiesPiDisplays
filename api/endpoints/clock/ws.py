import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from helpers.config import read_settings
from .ws_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def clock_ws(websocket: WebSocket):
    settings = read_settings()
    await manager.connect(websocket, settings.get("clock", {}))
    logger.info("Clock display connected via WebSocket")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Clock display disconnected")
