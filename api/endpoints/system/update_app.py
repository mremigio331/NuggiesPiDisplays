import logging
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.system import SystemManager

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
    """
    scoped = bool(req.component) and req.component != "all"
    logger.info(
        "App update requested (run_setup=%s component=%s force=%s)",
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
    )
    return JSONResponse(
        {
            "message": (
                "Update started. Pi will reboot shortly."
                if not scoped
                else f"Updating {req.component}. The affected service will restart."
            ),
            "run_setup": req.run_setup,
            "component": req.component or "all",
            "force": req.force,
            "setup_mode": (
                ("--update" if not scoped else f"--update-{req.component}")
                if req.run_setup
                else None
            ),
        }
    )
