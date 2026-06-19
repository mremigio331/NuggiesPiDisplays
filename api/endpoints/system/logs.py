import logging
from pathlib import Path
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, PlainTextResponse

logger = logging.getLogger(__name__)
router = APIRouter()

_LOG_DIR = Path("/var/log/nuggies")

# Allowlisted log files — prevents arbitrary file reads
_ALLOWED_LOGS = {
    "application": _LOG_DIR / "application.log",
    "display": _LOG_DIR / "display.log",
    "service": _LOG_DIR / "service.log",
    "wifi": _LOG_DIR / "wifi_setup.log",
}


@router.get("/logs")
async def list_logs():
    """Return available log files and their sizes."""
    logs = []
    for key, path in _ALLOWED_LOGS.items():
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        logs.append({"key": key, "name": path.name, "exists": exists, "size": size})
    return JSONResponse({"logs": logs})


@router.get("/logs/{log_key}")
async def get_log(
    log_key: str,
    lines: int = Query(default=100, ge=1, le=1000),
):
    """Return the last N lines of a log file."""
    if log_key not in _ALLOWED_LOGS:
        return JSONResponse(
            {"error": f"Unknown log. Available: {sorted(_ALLOWED_LOGS.keys())}"},
            status_code=404,
        )

    path = _ALLOWED_LOGS[log_key]
    if not path.exists():
        return PlainTextResponse("(log file does not exist yet)\n")

    try:
        # Read last N lines efficiently
        content = path.read_text(errors="replace")
        all_lines = content.splitlines()
        tail = all_lines[-lines:]
        return PlainTextResponse("\n".join(tail) + "\n")
    except Exception as e:
        logger.error(f"Failed to read log {log_key}: {e}")
        return PlainTextResponse(f"Error reading log: {e}\n", status_code=500)
