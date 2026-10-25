import logging
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.system import SystemManager, new_run_id, take_update_lock

logger = logging.getLogger(__name__)
router = APIRouter()


class UpdateRequest(BaseModel):
    run_setup: bool = True
    # Scope the update to one component (api/display/website/system). None or
    # "all" runs the full update. force=true reinstalls even if it didn't change.
    component: str | None = None
    force: bool = False


@router.post("/update-app")
async def update_app(req: UpdateRequest, background_tasks: BackgroundTasks):
    """Pull latest code, re-run the lightweight updater, then reboot.

    Uses setup.sh --update (or --update-<component>) rather than the full
    --dev/--prod installer, which re-runs apt upgrades / node install and
    self-reboots — too heavy and failure-prone for an in-field update.

    Each call mints a run_id (UUID) and takes an exclusive update lock. If an
    update is already running, the call does NOT start a second one — it returns
    409 with the ACTIVE run_id so the client attaches to the run in progress.
    The client polls /update-log?run_id=<id> and shows only its own run's output.
    """
    scoped = bool(req.component) and req.component != "all"
    setup_mode = (
        ("--update" if not scoped else f"--update-{req.component}")
        if req.run_setup
        else None
    )

    # Mint this run's id and take the lock ATOMICALLY before scheduling anything.
    run_id = new_run_id()
    active = take_update_lock(run_id, setup_mode or "--update")
    if active is not None:
        # An update is already running. Don't start a second — hand the client
        # the in-flight run_id so it can follow that one instead.
        logger.info(
            "Update requested but one is already running (active run_id=%s)",
            active.get("run_id"),
        )
        return JSONResponse(
            {
                "message": "An update is already running.",
                "already_running": True,
                "run_id": active.get("run_id"),
                "started": active.get("started"),
            },
            status_code=409,
        )

    logger.info(
        "App update requested (run_id=%s run_setup=%s component=%s force=%s)",
        run_id,
        req.run_setup,
        req.component or "all",
        req.force,
    )
    background_tasks.add_task(
        SystemManager().update_app,
        req.run_setup,
        "--update",
        req.component,
        req.force,
        run_id,
    )
    return JSONResponse(
        {
            "message": (
                "Update started. Pi will reboot shortly."
                if not scoped
                else f"Updating {req.component}. The affected service will restart."
            ),
            "run_id": run_id,
            "run_setup": req.run_setup,
            "component": req.component or "all",
            "force": req.force,
            "setup_mode": setup_mode,
        }
    )
