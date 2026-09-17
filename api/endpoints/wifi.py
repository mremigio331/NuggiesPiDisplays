"""WiFi status / networks routes for the MAIN API (port 8000, runs as ``pi``).

These are the real ``/api/wifi/*`` routes. Registered in ``api/main.py`` under the ``/api``
prefix and, critically, BEFORE the SPA catch-all so an unmatched ``/api/wifi/...`` resolves
to a real JSON route instead of the HTML shell.

============================================================================
Constraint — this route MUST NOT attempt ``nmcli device wifi rescan``.
============================================================================
The main API runs as ``pi``. A rescan there fails with
``org.freedesktop.NetworkManager.wifi.scan request failed: not authorized``, and ``nmcli``
is a deliberate sudoers non-grant (setup.sh task 1.1), so this cannot — and must not — be
"fixed" with sudo. When a network list is wanted from port 8000, serve the cached
``wifi_setup/.last_scan.json`` written by the boot script (as root, before the hotspot) or
answer ``409``. This device is the *configured* case, so ``409 setup_not_needed`` is the
primary behaviour. Do NOT reintroduce a rescan on this path.

Status derivation is intentionally CHEAP and read-only. It does NOT call
``resolve_verdict()`` — that resolver polls wlan0 for up to ``SETTLE_TIMEOUT_S`` (45s) and
rewrites the ``.wifi_configured`` cache. On the main API the device is already connected, so
a status probe must stay responsive: ``configured`` is read from the marker, ``connected``
from ``is_connected()``, and ``ssid`` from a read-only ``nmcli device status`` parse (no
rescan). None of these mutate state.
"""

import logging
import socket

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from helpers.wifi_state import WIFI_FLAG, FORCE_PORTAL

# The shared resolver owns the read-only wlan0 status parse; reuse it rather than
# duplicating the nmcli invocation. This is the DEVICE,STATE,CONNECTION read (no rescan).
from wifi_setup import wifi_manager
from wifi_setup.wifi_state import _wlan_status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wifi", tags=["wifi"])


def _derive_address() -> dict:
    """Derive this device's advertised address from its hostname — never hardcoded.

    ``hostname`` = ``socket.gethostname()``; ``mdns_name`` = ``<hostname>.local``; ``ip`` =
    the primary non-loopback IPv4 address, or ``None`` when there is none. The IP is read
    without any rescan: a UDP socket "connected" to an off-box address forces the OS to pick
    the outbound interface, and ``getsockname()`` reveals its local address. No packet is
    sent (UDP connect is purely a routing-table lookup).
    """
    hostname = socket.gethostname()
    return {
        "hostname": hostname,
        "mdns_name": f"{hostname}.local",
        "ip": _primary_ipv4(),
    }


def _primary_ipv4() -> str | None:
    """Best-effort primary non-loopback IPv4 address, or ``None``. Read-only, no rescan."""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 203.0.113.1 is TEST-NET-3 (RFC 5737) — never routed anywhere; this only asks the
        # kernel which local interface WOULD be used, without emitting traffic.
        sock.connect(("203.0.113.1", 9))
        ip = sock.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
        return None
    except Exception:
        return None
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


@router.get("/status")
async def wifi_status():
    """Cheap, read-only WiFi status plus this device's derived address.

    Shape mirrors the captive portal's ``/api/wifi/status`` so a client can consume one
    shape from either port.
    """
    configured = WIFI_FLAG.exists()
    connected = wifi_manager.is_connected()

    # Read-only wlan0 status parse (no rescan). Report the active connection name as the
    # SSID only when wlan0 is actually connected; otherwise leave it None.
    state, connection = _wlan_status()
    ssid = connection if (state or "").strip().lower() == "connected" else None

    # The portal is "active" whenever setup is being served: explicitly forced, or the
    # device is not configured. This mirrors the boot verdict without invoking the resolver.
    portal_active = FORCE_PORTAL.exists() or not configured

    body = {
        "configured": configured,
        "connected": connected,
        "ssid": ssid,
        "portal_active": portal_active,
    }
    body.update(_derive_address())
    return JSONResponse(body)


@router.get("/networks")
async def wifi_networks():
    """Network list for the setup flow.

    On the main API the device is configured, so setup is not needed: answer ``409`` with
    ``{"code": "setup_not_needed"}``. This route deliberately does NOT rescan (see the
    module docstring) — the only list it could serve here is the cached scan, and while
    configured the correct answer is the 409.
    """
    if WIFI_FLAG.exists():
        return JSONResponse({"code": "setup_not_needed"}, status_code=409)

    # Not configured (unusual on the main API, but handle it): serve ONLY the cached scan
    # written by the boot script. Never rescan here.
    networks = wifi_manager._cached_networks()
    return JSONResponse({"networks": networks, "stale": True})
