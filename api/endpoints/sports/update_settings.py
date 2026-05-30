import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.config import read_settings, write_settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Extend this set when adding new sports (NFL, NHL, …)
_VALID_SPORTS = {"nba", "mlb", "nhl"}
_VALID_DISPLAY_MODES = {"focus", "overview"}


class SportsSettingsBody(BaseModel):
    favorite_teams: list[str] | None = None
    cycle_interval_seconds: int | None = None
    sport: str | None = None
    display_mode: str | None = None


@router.put("/settings")
async def update_sports_settings(body: SportsSettingsBody):
    if body.cycle_interval_seconds is not None and not (
        5 <= body.cycle_interval_seconds <= 120
    ):
        return JSONResponse(
            {"error": "cycle_interval_seconds must be 5–120"}, status_code=422
        )
    if body.sport is not None and body.sport not in _VALID_SPORTS:
        return JSONResponse(
            {"error": f"sport must be one of {sorted(_VALID_SPORTS)}"}, status_code=422
        )
    if body.display_mode is not None and body.display_mode not in _VALID_DISPLAY_MODES:
        return JSONResponse(
            {"error": f"display_mode must be one of {sorted(_VALID_DISPLAY_MODES)}"},
            status_code=422,
        )

    settings = read_settings()
    sports = settings.setdefault("sports", {})
    if body.favorite_teams is not None:
        sports["favorite_teams"] = [t.upper() for t in body.favorite_teams]
    if body.cycle_interval_seconds is not None:
        sports["cycle_interval_seconds"] = body.cycle_interval_seconds
    if body.sport is not None:
        sports["sport"] = body.sport
    if body.display_mode is not None:
        sports["display_mode"] = body.display_mode
    write_settings(settings)
    logger.info(f"Sports settings updated: {sports}")
    return JSONResponse(sports)
