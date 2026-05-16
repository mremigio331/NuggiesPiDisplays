import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

logger = logging.getLogger(__name__)
router = APIRouter()

_DIST = Path(__file__).resolve().parent.parent.parent / "website" / "dist"


@router.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    candidate = _DIST / full_path
    if candidate.is_file():
        return FileResponse(str(candidate))
    index = _DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return Response(
        "Frontend not built. Run npm run build in website/.", status_code=503
    )
