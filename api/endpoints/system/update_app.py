import asyncio
import logging
import subprocess

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from helpers.dev_config import is_dev_mode
from helpers.process import _PROJECT_ROOT

logger = logging.getLogger(__name__)
router = APIRouter()


class UpdateRequest(BaseModel):
    run_setup: bool = True


async def _do_update(run_setup: bool) -> None:
    await asyncio.sleep(1)  # let the HTTP response go out first

    logger.info("Running git pull...")
    pull = subprocess.run(
        ["git", "-C", str(_PROJECT_ROOT), "pull"],
        capture_output=True,
        text=True,
    )
    logger.info("git pull stdout: %s", pull.stdout.strip())
    if pull.returncode != 0:
        logger.warning("git pull stderr: %s", pull.stderr.strip())

    if run_setup:
        mode = "--dev" if is_dev_mode() else "--prod"
        logger.info("Running setup.sh %s...", mode)
        subprocess.run(
            ["sudo", "bash", str(_PROJECT_ROOT / "setup.sh"), mode],
            cwd=str(_PROJECT_ROOT),
        )

    logger.info("Rebooting Pi after update...")
    subprocess.run(["sudo", "reboot"])


@router.post("/update-app")
async def update_app(req: UpdateRequest, background_tasks: BackgroundTasks):
    """Pull latest code, optionally re-run setup, then reboot."""
    mode = "--dev" if is_dev_mode() else "--prod"
    logger.info("App update requested (run_setup=%s, mode=%s)", req.run_setup, mode)
    background_tasks.add_task(_do_update, req.run_setup)
    return JSONResponse(
        {
            "message": "Update started. Pi will reboot shortly.",
            "run_setup": req.run_setup,
            "setup_mode": mode if req.run_setup else None,
        }
    )
