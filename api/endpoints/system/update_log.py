import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from helpers.logger import LOG_DIR
from helpers.system import _UPDATE_LOG_START

logger = logging.getLogger(__name__)
router = APIRouter()

_UPDATE_LOG = LOG_DIR / "update.log"


@router.get("/update-log")
async def update_log(offset: int = 0, run_id: str = ""):
    """Return update.log bytes from *offset* onward, for incremental polling.

    The UI opens a modal on Update and polls this endpoint, appending each new
    chunk to a live progress view. Returning a byte offset (rather than streaming)
    keeps the client trivially reconnect-safe across the mid-update API restart /
    reboot: the client just re-requests from its last offset once the API is back.

    The current run's id is parsed from the start sentinel
    (``=== NUGGIES UPDATE START === <run_id> <flags>``). When the caller passes
    its own *run_id*, ``match`` says whether the log on disk is THAT run — so the
    UI can ignore a previous run's leftover output and show only the update the
    user just kicked off.

    Response fields:
      - exists:  whether update.log is present yet
      - started: whether the current log begins with the fresh-run sentinel
      - run_id:  the run id parsed from the log's sentinel (empty if none)
      - match:   whether the log's run_id equals the caller's run_id
      - offset:  the new offset the client should send on its next poll
      - size:    current file size in bytes
      - content: the text between the requested offset and end of file
    """
    if not _UPDATE_LOG.exists():
        return JSONResponse(
            {
                "exists": False,
                "started": False,
                "run_id": "",
                "match": False,
                "offset": 0,
                "size": 0,
                "content": "",
            }
        )

    size = _UPDATE_LOG.stat().st_size

    # If the file shrank since the client's last poll (a new run truncated it),
    # the client's offset is stale — reset to the start so it re-reads the new run.
    if offset > size:
        offset = 0

    log_run_id = ""
    try:
        with open(_UPDATE_LOG, "rb") as f:
            first = f.readline()
            started = first.startswith(_UPDATE_LOG_START.encode())
            if started:
                # Sentinel: "=== NUGGIES UPDATE START === <run_id> <flags>".
                # The token right after the sentinel prefix is the run id.
                rest = first.decode("utf-8", errors="replace")[
                    len(_UPDATE_LOG_START) :
                ].strip()
                log_run_id = rest.split(" ", 1)[0] if rest else ""
            f.seek(offset)
            data = f.read()
    except OSError as e:
        logger.warning(f"Could not read update.log: {e}")
        return JSONResponse(
            {
                "exists": True,
                "started": False,
                "run_id": "",
                "match": False,
                "offset": offset,
                "size": size,
                "content": "",
            }
        )

    text = data.decode("utf-8", errors="replace")
    # match is True when the caller didn't pin a run_id (legacy/attach-to-latest)
    # or when the log on disk is exactly the caller's run.
    match = (not run_id) or (log_run_id == run_id)
    return JSONResponse(
        {
            "exists": True,
            "started": started,
            "run_id": log_run_id,
            "match": match,
            "offset": size,
            "size": size,
            "content": text,
        }
    )
