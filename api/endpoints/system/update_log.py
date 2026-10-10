import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from helpers.logger import LOG_DIR
from helpers.system import _UPDATE_LOG_START

logger = logging.getLogger(__name__)
router = APIRouter()

_UPDATE_LOG = LOG_DIR / "update.log"


@router.get("/update-log")
async def update_log(offset: int = 0):
    """Return update.log bytes from *offset* onward, for incremental polling.

    The UI opens a modal on Update and polls this endpoint, appending each new
    chunk to a live progress view. Returning a byte offset (rather than streaming)
    keeps the client trivially reconnect-safe across the mid-update API restart /
    reboot: the client just re-requests from its last offset once the API is back.

    Response fields:
      - exists:  whether update.log is present yet
      - started: whether the current log begins with the fresh-run sentinel
      - offset:  the new offset the client should send on its next poll
      - size:    current file size in bytes
      - content: the text between the requested offset and end of file
    """
    if not _UPDATE_LOG.exists():
        return JSONResponse(
            {"exists": False, "started": False, "offset": 0, "size": 0, "content": ""}
        )

    size = _UPDATE_LOG.stat().st_size

    # If the file shrank since the client's last poll (a new run truncated it),
    # the client's offset is stale — reset to the start so it re-reads the new run.
    if offset > size:
        offset = 0

    try:
        with open(_UPDATE_LOG, "rb") as f:
            first = f.readline()
            started = first.startswith(_UPDATE_LOG_START.encode())
            f.seek(offset)
            data = f.read()
    except OSError as e:
        logger.warning(f"Could not read update.log: {e}")
        return JSONResponse(
            {
                "exists": True,
                "started": False,
                "offset": offset,
                "size": size,
                "content": "",
            }
        )

    text = data.decode("utf-8", errors="replace")
    return JSONResponse(
        {
            "exists": True,
            "started": started,
            "offset": size,
            "size": size,
            "content": text,
        }
    )
