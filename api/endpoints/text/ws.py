import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from helpers.config import normalize_text, read_settings
from .ws_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def text_ws(websocket: WebSocket):
    settings = read_settings()
    await manager.connect(websocket, normalize_text(settings.get("text")))
    logger.info("Text display connected via WebSocket")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Text display disconnected")
