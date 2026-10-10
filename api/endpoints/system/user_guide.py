import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from helpers.process import _PROJECT_ROOT

logger = logging.getLogger(__name__)
router = APIRouter()

_USER_GUIDE = _PROJECT_ROOT / "USER_GUIDE.md"


@router.get("/user-guide")
async def get_user_guide():
    """Return the USER_GUIDE.md markdown so the web UI can render it as a page.

    The guide lives in the repo root and is updated with each release, so serving
    it directly keeps the in-app manual in sync with the installed version.
    """
    if not _USER_GUIDE.exists():
        return JSONResponse(
            {"markdown": "", "error": "User guide not found."}, status_code=404
        )
    try:
        markdown = _USER_GUIDE.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        logger.error(f"Failed to read USER_GUIDE.md: {e}")
        return JSONResponse(
            {"markdown": "", "error": "Could not read user guide."}, status_code=500
        )
    return JSONResponse({"markdown": markdown})
