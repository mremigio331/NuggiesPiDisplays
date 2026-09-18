"""Shared configured-verdict resolver.

Single source of truth for "is this device configured?" — consumed identically by the
root boot script (``scripts/wifi_setup_service.sh``) and the ``pi`` API, so the setup-page
decision and the display auto-start decision can never disagree within a boot.

Importable as a module and runnable as a CLI::

    python3 -m wifi_setup.wifi_state --verdict

Resolution order (first match wins):

    1. ``.factory_wifi_reset`` present  -> unconfigured / wifi_wiped
    2. ``.force_portal`` present        -> unconfigured / forced
    3. Poll ``nmcli device status`` for wlan0 until its state leaves the transient set,
       bounded by SETTLE_TIMEOUT_S, corroborated by ``nmcli general`` connectivity:
         - settled ``connected`` on a profile other than the setup AP -> configured / client_associated (with SSID)
         - anything else after the full window                        -> unconfigured / no_association

The ``.wifi_configured`` marker is the resolver's CACHE, not an independent opinion: a
``configured`` verdict WRITES it, an ``unconfigured`` verdict REMOVES it.

Marker write strategy: the resolver runs as root from the boot script and as ``pi`` from
the API, so every marker it creates must end up owned by the project-root owner (``pi``),
and every write is UNLINK-THEN-CREATE, never open-for-write. ``pi`` can always unlink
inside the ``pi``-owned project root even when it cannot open a root-owned file for
writing, so unlink-then-create recovers from a stale root-owned marker instead of wedging.
When running as root, the marker is chowned to the project-root owner after creation.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from wifi_setup.ap_config import AP_CON_NAME

# --- Marker paths: the single definition of each, all at the project root. ---
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

WIFI_FLAG = _PROJECT_ROOT / ".wifi_configured"
FORCE_PORTAL = _PROJECT_ROOT / ".force_portal"
FACTORY_WIFI_RESET = _PROJECT_ROOT / ".factory_wifi_reset"

# --- Settle tuning. ---
SETTLE_TIMEOUT_S = 45
_POLL_INTERVAL_S = 1.5
_WLAN_IFACE = "wlan0"

# States that mean "wlan0 has not settled yet". A state in this set never yields an early
# verdict; it is only treated as unconfigured once the full SETTLE_TIMEOUT_S window elapses.
_TRANSIENT_STATES = frozenset(
    {
        "connecting",
        "config",
        "ip-config",
        "ip-check",
        "secondaries",
        "unavailable",
    }
)


@dataclass
class Verdict:
    """Structured resolver result shared by the CLI and importers."""

    verdict: str  # "configured" | "unconfigured"
    reason: str  # "client_associated" | "no_association" | "forced" | "wifi_wiped"
    ssid: str | None = None

    def as_dict(self) -> dict:
        return {"verdict": self.verdict, "reason": self.reason, "ssid": self.ssid}


# --------------------------------------------------------------------------- #
# Marker cache helpers (unlink-then-create, root-safe)
# --------------------------------------------------------------------------- #
def _target_owner() -> tuple[int, int]:
    """uid/gid the markers must end up owned by — the owner of the project root."""
    st = _PROJECT_ROOT.stat()
    return st.st_uid, st.st_gid


def _write_marker(path: Path) -> None:
    """Create *path* using unlink-then-create; hand it to the project-root owner if root.

    Never opens an existing file for writing: ``pi`` can unlink inside the ``pi``-owned
    project root even when the file itself is a stale root-owned marker, so this recovers
    instead of raising PermissionError.
    """
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    # O_CREAT|O_EXCL guarantees we are creating a fresh file we own, not reusing one.
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    os.close(fd)
    # When running as root, the freshly created file is root-owned; hand it back to the
    # project-root owner so the pi API can maintain it later. As pi the ownership is
    # already correct, so skip the chown (which pi is not allowed to perform anyway).
    if os.geteuid() == 0:
        uid, gid = _target_owner()
        try:
            os.chown(str(path), uid, gid)
        except OSError:
            pass


def _remove_marker(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def mark_configured() -> None:
    """Write the ``.wifi_configured`` cache marker (unlink-then-create, root-safe)."""
    _write_marker(WIFI_FLAG)


def clear_configured() -> None:
    """Remove the ``.wifi_configured`` cache marker."""
    _remove_marker(WIFI_FLAG)


# --------------------------------------------------------------------------- #
# nmcli probes
# --------------------------------------------------------------------------- #
def _wlan_status() -> tuple[str | None, str | None]:
    """Return (state, connection) for wlan0 from ``nmcli device status``.

    Both values are lower-cased for state comparison purposes except the connection name,
    which is returned as-is so the reported SSID matches what NetworkManager shows.
    """
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "DEVICE,STATE,CONNECTION", "device", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return None, None

    for line in result.stdout.strip().splitlines():
        # DEVICE:STATE:CONNECTION — CONNECTION (an SSID/profile name) may contain colons,
        # so split off the first two fields from the left and keep the remainder intact.
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        device, state, connection = parts
        if device == _WLAN_IFACE:
            return state.strip(), connection.strip()
    return None, None


def _is_transient(state: str | None) -> bool:
    """True while wlan0 is still associating (any ``connecting`` variant, or another
    transient NM state). Covers ``connecting``, ``connecting:*``, and ``connecting (...)``.
    """
    if not state:
        # No wlan0 line at all — not transient, just not settled to connected.
        return False
    s = state.strip().lower()
    if s.startswith("connecting"):
        return True
    return s in _TRANSIENT_STATES


def _connectivity() -> str:
    """``nmcli -t -f CONNECTIVITY general`` -> lower-cased connectivity word."""
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "CONNECTIVITY", "general"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip().lower()
    except Exception:
        return "unknown"


def _has_saved_client_profile() -> bool:
    """True if a saved, autoconnect-eligible client wifi profile exists.

    "Client wifi profile" = a saved NM connection whose TYPE is wireless
    (``802-11-wireless``), whose NAME is not the setup AP (``AP_CON_NAME``), and whose
    AUTOCONNECT is ``yes``. Such a profile is exactly what NetworkManager auto-activates a
    few seconds into boot, so its presence is the signal that the settle loop has
    "something worth waiting for".

    Read-only. On any nmcli failure this returns ``True`` (err on the side of waiting): a
    false "wait" costs at most SETTLE_TIMEOUT_S, whereas a false "don't wait" would
    reintroduce the boot race this module guards against.
    """
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE,AUTOCONNECT", "connection", "show"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return True

    if result.returncode != 0:
        return True

    for line in result.stdout.strip().splitlines():
        # NAME:TYPE:AUTOCONNECT — NAME may contain colons, so split the two trailing
        # fields off from the right and keep the name intact.
        parts = line.rsplit(":", 2)
        if len(parts) != 3:
            continue
        name, ctype, autoconnect = parts
        name = name.strip()
        ctype = ctype.strip().lower()
        autoconnect = autoconnect.strip().lower()
        if "wireless" not in ctype:
            continue
        if name == AP_CON_NAME:
            continue
        if autoconnect == "yes":
            return True
    return False


# --------------------------------------------------------------------------- #
# Verdict resolution
# --------------------------------------------------------------------------- #
def _resolve_settle() -> Verdict:
    """Poll wlan0 until it settles on a client network (or the window elapses).

    Fixes a boot race: at T=0 the wifi-setup service runs this resolver while wlan0 is
    still ``disconnected`` — NetworkManager has not yet begun auto-activating the saved
    network. ``disconnected`` is not a transient NM state, so a naive "break as soon as
    the state is non-transient" check would return ``no_association`` instantly, and the
    boot script would tear down the good connection NM brings up ~3s later and boot into
    setup-AP mode despite a valid saved profile.

    To close that race the loop keeps waiting through BOTH transient states and plain
    not-yet-connected states (``disconnected``, ``unavailable``, empty) UNTIL the deadline
    — but only when there is something worth waiting for, i.e. a saved, non-AP,
    autoconnect-eligible client wifi profile exists (``_has_saved_client_profile``). A
    genuinely unconfigured device with no saved client profile is not made to sit through
    the full window every boot; it returns ``no_association`` promptly.

    Outcomes:
        - wlan0 ``connected`` on a profile other than AP_CON_NAME, corroborated by NM
          connectivity (full/limited/portal/unknown) -> configured / client_associated
        - wlan0 ``connected`` on AP_CON_NAME (the setup AP) is NOT a client association;
          keep waiting for autoconnect while a saved profile exists
        - deadline reached, or nothing worth waiting for -> unconfigured / no_association
    """
    deadline = time.monotonic() + SETTLE_TIMEOUT_S
    wait_for_autoconnect = _has_saved_client_profile()

    while True:
        state, connection = _wlan_status()
        s = (state or "").strip().lower()

        # Settled on a real (non-AP) client network?
        if s == "connected" and connection and connection != AP_CON_NAME:
            # Corroborate with NM's own connectivity view; treat full/limited as
            # associated. If NM reports no connectivity at all we do not claim configured.
            conn = _connectivity()
            if conn in ("full", "limited", "portal", "unknown"):
                return Verdict("configured", "client_associated", ssid=connection)

        # Not associated to a client network (yet). Decide whether to keep waiting.
        #   - transient states always keep waiting until the deadline
        #   - plain not-yet-connected states keep waiting only while a saved autoconnect
        #     profile exists (NM is likely about to bring it up)
        #   - connected-on-AP is not a client association; keep waiting for autoconnect
        #     while a saved profile exists
        still_waiting = _is_transient(state) or (
            wait_for_autoconnect and s != "connected"
        )
        if s == "connected" and connection == AP_CON_NAME and wait_for_autoconnect:
            still_waiting = True

        if not still_waiting:
            return Verdict("unconfigured", "no_association")
        if time.monotonic() >= deadline:
            return Verdict("unconfigured", "no_association")

        time.sleep(_POLL_INTERVAL_S)


def resolve_verdict() -> Verdict:
    """Resolve the configured verdict and refresh the ``.wifi_configured`` cache.

    First match wins:
        1. ``.factory_wifi_reset`` -> unconfigured / wifi_wiped
        2. ``.force_portal``       -> unconfigured / forced
        3. settle poll             -> configured / client_associated  OR  unconfigured / no_association
    """
    if FACTORY_WIFI_RESET.exists():
        result = Verdict("unconfigured", "wifi_wiped")
    elif FORCE_PORTAL.exists():
        result = Verdict("unconfigured", "forced")
    else:
        result = _resolve_settle()

    # The marker is the cache, not an independent opinion.
    if result.verdict == "configured":
        mark_configured()
    else:
        clear_configured()

    return result


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _print_verdict(result: Verdict) -> None:
    line = f"{result.verdict} {result.reason}"
    if result.ssid:
        line += f" {result.ssid}"
    print(line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wifi_setup.wifi_state",
        description="Resolve the shared configured verdict for this device.",
    )
    parser.add_argument(
        "--verdict",
        action="store_true",
        help="Print the resolved verdict and reason (and SSID when configured), then exit.",
    )
    args = parser.parse_args(argv)

    if args.verdict:
        _print_verdict(resolve_verdict())
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
