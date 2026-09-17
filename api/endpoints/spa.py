import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, Response

logger = logging.getLogger(__name__)
router = APIRouter()

_DIST = Path(__file__).resolve().parent.parent.parent / "website" / "dist"


@router.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    candidate = _DIST / full_path
    if candidate.is_file():
        return FileResponse(str(candidate))
    # An unmatched path under /api/ is a missing API route, not a client-side SPA route:
    # answer with a JSON 404 instead of the HTML shell at status 200 (which masked missing
    # routes as "success"). `full_path` has no leading slash, so match "api" / "api/...".
    if full_path == "api" or full_path.startswith("api/"):
        return JSONResponse({"code": "not_found"}, status_code=404)
    index = _DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return Response(
        "Frontend not built. Run npm run build in website/.", status_code=503
    )
