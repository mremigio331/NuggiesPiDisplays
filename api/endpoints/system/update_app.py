import logging
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from helpers.dev_config import is_dev_mode
from helpers.system import SystemManager

logger = logging.getLogger(__name__)
router = APIRouter()


class UpdateRequest(BaseModel):
    run_setup: bool = True


@router.post("/update-app")
async def update_app(req: UpdateRequest, background_tasks: BackgroundTasks):
    """Pull latest code, optionally re-run setup, then reboot."""
    mode = "--dev" if is_dev_mode() else "--prod"
    logger.info(f"App update requested (run_setup={req.run_setup}, mode={mode})")
    background_tasks.add_task(SystemManager().update_app, req.run_setup)
    return JSONResponse(
        {
            "message": "Update started. Pi will reboot shortly.",
            "run_setup": req.run_setup,
            "setup_mode": mode if req.run_setup else None,
        }
    )
