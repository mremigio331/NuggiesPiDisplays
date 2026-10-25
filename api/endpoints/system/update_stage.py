import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import read_update_stage, write_update_stage, VALID_UPDATE_STAGES

logger = logging.getLogger(__name__)
router = APIRouter()


class StageRequest(BaseModel):
    stage: str


@router.get("/update-stage")
async def get_update_stage():
    """Which release stage this device tracks: 'beta' or 'prod' (default prod)."""
    return JSONResponse(
        {"stage": read_update_stage(), "valid": list(VALID_UPDATE_STAGES)}
    )


@router.put("/update-stage")
async def set_update_stage(req: StageRequest):
    """Switch the device between the 'beta' and 'prod' release streams."""
    try:
        stage = write_update_stage(req.stage)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    logger.info("Update stage set to %s", stage)
    return JSONResponse({"stage": stage})
