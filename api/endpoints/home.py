import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def home():
    return JSONResponse({"status": "ok", "service": "nuggies-pi-displays"})
