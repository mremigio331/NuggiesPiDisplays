from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import wifi_manager

PROJECT_DIR = Path(__file__).parent.parent
DIST_DIR = PROJECT_DIR / "website" / "dist"
INDEX_HTML = DIST_DIR / "index.html"

# Paths used by iOS/macOS/Android/Windows to detect captive portals.
# Redirect all of them to the setup page.
_CAPTIVE_PROBES = frozenset(
    {
        "/hotspot-detect.html",
        "/library/test/success.html",
        "/generate_204",
        "/gen_204",
        "/connecttest.txt",
        "/ncsi.txt",
        "/redirect",
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
# WiFi API
# ---------------------------------------------------------------------------


@app.get("/api/wifi/networks")
async def get_networks():
    return wifi_manager.scan_networks()


@app.post("/api/wifi/connect")
async def connect_wifi(req: ConnectRequest, background_tasks: BackgroundTasks):
    result = wifi_manager.connect_to_network(req.ssid, req.password)
    if result["success"]:
        background_tasks.add_task(_finalize_after_connect)
    return result


@app.get("/api/wifi/status")
async def get_status():
    return {"connected": wifi_manager.is_connected()}


async def _finalize_after_connect() -> None:
    """Wait for WiFi to stabilize, then reboot so the display starts cleanly with internet."""
    await asyncio.sleep(5)
    subprocess.run(["systemctl", "reboot"])


# ---------------------------------------------------------------------------
# Static file / SPA catch-all
# ---------------------------------------------------------------------------


@app.get("/{full_path:path}")
async def serve_spa(request: Request, full_path: str) -> Response:
    path = "/" + full_path

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

    # SPA fallback — let React Router handle the path.
    if INDEX_HTML.exists():
        return FileResponse(str(INDEX_HTML))

    return Response(
        "WiFi Setup Portal — React build not found. Run 'npm run build' in website/.",
        status_code=503,
    )
