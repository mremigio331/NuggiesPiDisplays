import logging
from typing import Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import read_settings, write_settings

logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}

router = APIRouter(prefix="/configs", tags=["mta"])


@router.get("")
async def get_configs():
    settings = read_settings()
    return JSONResponse(settings.get("mta", {}))


class ConfigUpdate(BaseModel):
    key: str
    value: Any


@router.put("")
async def update_config(body: ConfigUpdate):
    key, value = body.key, body.value

    if key == "log_level" and value not in VALID_LOG_LEVELS:
        raise HTTPException(
            status_code=422, detail=f"log_level must be one of {VALID_LOG_LEVELS}"
        )
    if key == "cycle_time":
        try:
            if int(str(value)) <= 0:
                raise ValueError
        except ValueError:
            raise HTTPException(
                status_code=422, detail="cycle_time must be a positive integer string"
            )

    settings = read_settings()
    mta = settings.get("mta", {})
    if key not in mta:
        raise HTTPException(status_code=400, detail=f"Unknown config key: {key}")

    mta[key] = value
    settings["mta"] = mta
    write_settings(settings)
    logger.info("Subway config updated: %s = %r", key, value)
    return JSONResponse({"key": key, "value": value})
