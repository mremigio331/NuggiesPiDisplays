import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import read_settings, write_settings

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_CYCLE_KEYS = {"intraday", "6month", "ytd", "1year"}


class StocksSettings(BaseModel):
    stock_abbrs: Optional[List[str]] = None
    interval_seconds: Optional[int] = None
    display_brightness: Optional[int] = None
    market_hours_only: Optional[bool] = None
    timezone: Optional[str] = None
    stock_cycles: Optional[list] = None


@router.put("/settings")
async def update_settings(body: StocksSettings):
    updates = body.model_dump(exclude_none=True)

    if "stock_abbrs" in updates:
        abbrs = updates["stock_abbrs"]
        if not (1 <= len(abbrs) <= 5) or not all(
            isinstance(s, str) and s.strip() for s in abbrs
        ):
            raise HTTPException(
                status_code=422, detail="stock_abbrs must be 1-5 non-empty strings"
            )
        updates["stock_abbrs"] = [s.upper() for s in abbrs]

    if "interval_seconds" in updates and not (10 <= updates["interval_seconds"] <= 300):
        raise HTTPException(status_code=422, detail="interval_seconds must be 10-300")

    if "display_brightness" in updates and not (
        0 <= updates["display_brightness"] <= 100
    ):
        raise HTTPException(status_code=422, detail="display_brightness must be 0-100")

    if "timezone" in updates:
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(updates["timezone"])
        except Exception:
            raise HTTPException(
                status_code=422, detail=f"Invalid timezone: {updates['timezone']}"
            )

    if "stock_cycles" in updates:
        for cycle in updates["stock_cycles"]:
            if cycle.get("key") not in VALID_CYCLE_KEYS:
                raise HTTPException(
                    status_code=422, detail=f"Invalid cycle key: {cycle.get('key')}"
                )

    settings = read_settings()
    stocks = settings.get("stocks", {})
    stocks.update(updates)
    settings["stocks"] = stocks
    write_settings(settings)
    logger.info(f"Stocks settings updated: {list(updates.keys())}")
    return JSONResponse(stocks)
