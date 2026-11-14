import logging
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from constants import DISPLAY_MODES
from helpers.config import (
    CYCLE_ALL_OPTION,
    CYCLE_MAX_MINUTES,
    CYCLE_MAX_NAME_LENGTH,
    CYCLE_MIN_MINUTES,
    cycle_steps,
    normalize_cycle,
    read_cycles,
    read_settings,
    schedule_mode_options,
    set_active_cycle,
    write_cycles,
    write_settings,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class CycleView(BaseModel):
    mode: str
    option: str | None = None


class CycleBody(BaseModel):
    name: str
    minutes: int
    views: list[CycleView]


def _payload(cycles: dict) -> dict:
    """Saved cycles plus the UI's dropdown vocabularies, all backend-owned."""
    return {
        **cycles,
        "modes": DISPLAY_MODES,
        "mode_options": schedule_mode_options(),
        "all_option": CYCLE_ALL_OPTION,
        "minutes": {"min": CYCLE_MIN_MINUTES, "max": CYCLE_MAX_MINUTES},
        "max_name_length": CYCLE_MAX_NAME_LENGTH,
    }


def _validated(cycle_id: str, body: CycleBody) -> dict:
    if not (CYCLE_MIN_MINUTES <= body.minutes <= CYCLE_MAX_MINUTES):
        raise HTTPException(
            status_code=422,
            detail=f"minutes must be between {CYCLE_MIN_MINUTES} and {CYCLE_MAX_MINUTES}",
        )
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Give the cycle a name")
    if len(body.name.strip()) > CYCLE_MAX_NAME_LENGTH:
        raise HTTPException(status_code=422, detail="That name is too long")
    cycle = normalize_cycle({"id": cycle_id, **body.model_dump()})
    if cycle is None or len(cycle_steps(cycle)) < 2:
        raise HTTPException(status_code=422, detail="A cycle needs at least 2 views")
    return cycle


@router.get("/cycles")
async def get_cycles():
    return JSONResponse(_payload(read_cycles()))


@router.post("/cycles")
async def create_cycle(body: CycleBody):
    cycle = _validated(uuid.uuid4().hex[:12], body)
    cycles = read_cycles()
    cycles["saved"].append(cycle)
    logger.info("Cycle saved: %s", cycle["name"])
    return JSONResponse(_payload(write_cycles(cycles)))


@router.put("/cycles/{cycle_id}")
async def update_cycle(cycle_id: str, body: CycleBody):
    cycle = _validated(cycle_id, body)
    cycles = read_cycles()
    if cycle_id not in {c["id"] for c in cycles["saved"]}:
        raise HTTPException(status_code=404, detail="Cycle not found")
    cycles["saved"] = [cycle if c["id"] == cycle_id else c for c in cycles["saved"]]
    return JSONResponse(_payload(write_cycles(cycles)))


@router.delete("/cycles/{cycle_id}")
async def delete_cycle(cycle_id: str):
    settings = read_settings()
    schedule = settings.get("schedule")
    if isinstance(schedule, dict):
        # A schedule rule can't point at a cycle that no longer exists.
        schedule["rules"] = [
            r for r in schedule.get("rules", []) if r.get("cycle") != cycle_id
        ]
        write_settings(settings)
    cycles = read_cycles()
    cycles["saved"] = [c for c in cycles["saved"] if c["id"] != cycle_id]
    return JSONResponse(_payload(write_cycles(cycles)))


@router.post("/cycles/stop")
async def stop_cycle():
    set_active_cycle(None)
    return JSONResponse(_payload(read_cycles()))


@router.post("/cycles/{cycle_id}/start")
async def start_cycle(cycle_id: str):
    if not set_active_cycle(cycle_id):
        raise HTTPException(status_code=404, detail="Cycle not found")
    return JSONResponse(_payload(read_cycles()))
