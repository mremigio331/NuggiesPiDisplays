import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from helpers.dev_config import is_dev_mode

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dev-mode")
async def get_dev_mode():
    return JSONResponse({"dev_mode": is_dev_mode()})
