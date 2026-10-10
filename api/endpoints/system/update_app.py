import logging
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.system import SystemManager

logger = logging.getLogger(__name__)
router = APIRouter()


class UpdateRequest(BaseModel):
    run_setup: bool = True


@router.post("/update-app")
async def update_app(req: UpdateRequest, background_tasks: BackgroundTasks):
    """Pull latest code, re-run the lightweight updater, then reboot.

    Uses setup.sh --update (reinstall deps, rebuild frontend, reapply sudoers,
    restart service) rather than the full --dev/--prod installer, which re-runs
    apt upgrades / node install and self-reboots — too heavy and failure-prone
    for an in-field update triggered from the UI.
    """
    logger.info(f"App update requested (run_setup={req.run_setup})")
    background_tasks.add_task(SystemManager().update_app, req.run_setup, "--update")
    return JSONResponse(
        {
            "message": "Update started. Pi will reboot shortly.",
            "run_setup": req.run_setup,
            "setup_mode": "--update" if req.run_setup else None,
        }
    )
