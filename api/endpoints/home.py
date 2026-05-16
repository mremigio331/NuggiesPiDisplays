import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/health")
async def health():
    return JSONResponse({"status": "ok", "service": "nuggies-pi-displays"})
