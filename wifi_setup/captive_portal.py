from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import wifi_manager

# The visible setup-AP SSID, derived at runtime from the hostname (never hardcoded). Surfaced
# in the status response so the frontend can name the setup network correctly.
from .ap_config import AP_SSID

PROJECT_DIR = Path(__file__).parent.parent
DIST_DIR = PROJECT_DIR / "website" / "dist"
INDEX_HTML = DIST_DIR / "index.html"

# Paths used by iOS/macOS/Android/Windows to detect captive portals.
# Redirect all of them to the setup page.
_CAPTIVE_PROBES = frozenset(
    {
        "/hotspot-detect.html",
        "/library/test/success.html",
        "/success.txt",
        "/generate_204",
        "/gen_204",
        "/connecttest.txt",
        "/ncsi.txt",
        "/redirect",
        "/fwlink",
        "/fwlink/",
        "/wpad.dat",
    }
)

app = FastAPI(docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class ConnectRequest(BaseModel):
    ssid: str
    password: str | None = None


# ---------------------------------------------------------------------------
# Connect job tracking
# ---------------------------------------------------------------------------
#
# ``connect_to_network`` is a blocking call that hands the radio over from the setup
# AP to the target network — up to ~85s worst case, and once it stops the hotspot the
# HTTP client (a phone joined to the AP) loses its link. If we ran it inline the 202/200
# response would never reach the browser: the AP drops mid-request. So we return a job
# id *before* touching the radio, run the blocking handover in a background thread (via
# ``run_in_executor``), and let the client poll ``/api/wifi/connect/status`` for the real
# outcome once it reconnects.
#
# Single-worker uvicorn on port 80 means a plain module-level dict is enough — there is
# no cross-process state to reconcile. ``_LATEST_JOB_ID`` lets a client that lost its id
# (because the AP dropped before it read the 202 body) still recover the outcome.

_JOBS: dict[str, dict] = {}
_LATEST_JOB_ID: str | None = None


def _run_connect_job(job_id: str, ssid: str, password: str | None) -> None:
    """Perform the blocking radio handover, then record the outcome on the job.

    Runs in an executor thread. ``connect_to_network`` returns
    ``{"state": connected_verified|unknown_verify|failed, "ssid": ..., "message": ...}``;
    we map that ``state`` straight through. Any exception marks the job ``failed`` with the
    message so the record never stays stuck on ``connecting``. The post-connect reboot is
    scheduled here — only on ``connected_verified`` — because the reboot decision depends on
    the verified outcome, not on any (now removed) ``success`` flag.
    """
    try:
        result = wifi_manager.connect_to_network(ssid, password)
        _JOBS[job_id].update(
            state=result.get("state", "failed"),
            ssid=result.get("ssid", ssid),
            message=result.get("message", ""),
        )
        if result.get("state") == "connected_verified":
            # Preservation 3.4: a verified join records config (done inside
            # connect_to_network) and reboots into normal operation with the display up.
            asyncio.run(_finalize_after_connect())
    except (
        Exception
    ) as exc:  # noqa: BLE001 — never leave the job wedged on "connecting"
        _JOBS[job_id].update(state="failed", ssid=ssid, message=str(exc))


# ---------------------------------------------------------------------------
# WiFi API
# ---------------------------------------------------------------------------


@app.get("/api/wifi/networks")
async def get_networks():
    """Serve the scan result, surfacing staleness instead of an empty list (task 4.2).

    ``scan_networks()`` now returns ``{"networks": [...], "stale": bool, "error": ...}``.
    A live rescan cannot be serviced while wlan0 hosts the setup AP, so on that (expected)
    failure ``scan_networks()`` falls back to the ``wifi_setup/.last_scan.json`` cache and
    reports ``stale: true``. When stale, enrich the response with the cache's age (seconds
    since ``scanned_at``) so the client (task 6.2) can render
    "showing cached results from Ns ago".
    """
    result = wifi_manager.scan_networks()
    if result.get("stale"):
        age = _cache_age_seconds()
        if age is not None:
            result["age_seconds"] = age
    return result


def _cache_age_seconds() -> int | None:
    """Age in whole seconds of the ``LAST_SCAN_CACHE`` scan, or ``None`` if unavailable."""
    try:
        payload = json.loads(wifi_manager.LAST_SCAN_CACHE.read_text())
    except (OSError, ValueError):
        return None
    scanned_at = payload.get("scanned_at") if isinstance(payload, dict) else None
    if not isinstance(scanned_at, (int, float)):
        return None
    return max(0, int(time.time() - scanned_at))


@app.post("/api/wifi/connect")
async def connect_wifi(req: ConnectRequest):
    """Kick off the radio handover in the background and return a job id immediately.

    Returns ``202`` with ``{"job_id", "state": "connecting"}`` *before* the radio moves so
    the response reaches the browser while the AP is still up (bug condition:
    http_response_reached_client=false). The client then polls
    ``/api/wifi/connect/status`` for the real outcome.
    """
    global _LATEST_JOB_ID

    job_id = uuid.uuid4().hex
    _JOBS[job_id] = {"state": "connecting", "ssid": req.ssid, "message": ""}
    _LATEST_JOB_ID = job_id

    # Run the blocking, sequenced handover off the event loop so this handler returns now.
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _run_connect_job, job_id, req.ssid, req.password)

    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "state": "connecting"},
    )


@app.get("/api/wifi/connect/status")
async def connect_status(job_id: str | None = None):
    """Report a connect job's current state so the client can poll for the outcome.

    Query by ``?job_id=``; with no id, fall back to the most recent job — a client that
    lost its id after the AP dropped can still recover the result. States mirror
    ``connect_to_network``: ``connecting`` / ``connected_verified`` / ``unknown_verify`` /
    ``failed``.
    """
    if job_id is None:
        job_id = _LATEST_JOB_ID

    job = _JOBS.get(job_id) if job_id is not None else None
    if job is None:
        return JSONResponse(
            status_code=404,
            content={"state": "unknown", "message": "No connect job found."},
        )

    return {
        "job_id": job_id,
        "state": job["state"],
        "ssid": job.get("ssid"),
        "message": job.get("message", ""),
    }


def _derive_address() -> dict:
    """This device's advertised address, derived from its hostname — never hardcoded.

    Symmetric with the main API's ``/api/wifi/status`` (``api/endpoints/wifi.py``) so the
    client can consume one shape from either port. ``hostname`` = ``socket.gethostname()``;
    ``mdns_name`` = ``<hostname>.local``; ``ip`` = the primary non-loopback IPv4 address, or
    ``None``. The IP is read without any traffic: a UDP socket "connected" to an off-box
    address only forces the kernel to pick the outbound interface.
    """
    hostname = socket.gethostname()
    ip = None
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 203.0.113.1 is TEST-NET-3 (RFC 5737): never routed, so no packet is sent.
        sock.connect(("203.0.113.1", 9))
        candidate = sock.getsockname()[0]
        if candidate and not candidate.startswith("127."):
            ip = candidate
    except Exception:
        ip = None
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
    return {"hostname": hostname, "mdns_name": f"{hostname}.local", "ip": ip}


@app.get("/api/wifi/status")
async def get_status():
    body = {"connected": wifi_manager.is_connected(), "setup_ssid": AP_SSID}
    body.update(_derive_address())
    return body


async def _finalize_after_connect() -> None:
    """Wait for WiFi to stabilize, then reboot so the display starts cleanly with internet."""
    await asyncio.sleep(5)
    subprocess.run(["systemctl", "reboot"])


# ---------------------------------------------------------------------------
# Static file / SPA catch-all
# ---------------------------------------------------------------------------


@app.get("/{full_path:path}")
async def serve_spa(request: Request, full_path: str) -> Response:
    path = "/" + full_path.strip("/") if full_path else "/"

    # Android connectivity checks expect a real 204 — anything else confuses the detector.
    if path in {"/generate_204", "/gen_204"}:
        return Response(status_code=204)

    # All other OS probes and bare root: redirect to setup page.
    if path in _CAPTIVE_PROBES or path == "/":
        return RedirectResponse("/wifi-setup", status_code=302)

    # Serve a matching built asset if it exists.
    if full_path:
        candidate = DIST_DIR / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))

    # Keep the setup route as an SPA page.
    if INDEX_HTML.exists():
        if path == "/wifi-setup":
            return FileResponse(str(INDEX_HTML))
        # Unknown paths are almost always probe URLs from clients/OSes.
        # Force them onto the setup page instead of React's 404 route.
        return RedirectResponse("/wifi-setup", status_code=302)

    return Response(
        "WiFi Setup Portal — React build not found. Run 'npm run build' in website/.",
        status_code=503,
    )
