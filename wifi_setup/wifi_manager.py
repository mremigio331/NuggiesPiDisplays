from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from wifi_setup.ap_config import AP_SSID, AP_PASSWORD, AP_CON_NAME, AP_IP
from wifi_setup.wifi_state import WIFI_FLAG, mark_configured

# Module logger. The captive portal runs under uvicorn (as root) which configures root
# logging, so INFO/WARNING here surface in journalctl -u nuggies-wifi-setup.service.
logger = logging.getLogger(__name__)
# uvicorn sets this logger's effective level to WARNING+, which suppresses our INFO
# handover trace. Attach our own stderr handler (uvicorn captures stderr -> journalctl) and
# force INFO so the full connect/verify narration is visible regardless of uvicorn config.
# propagate=False avoids double-logging through the root/uvicorn handlers.
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(
        logging.Formatter("%(asctime)s wifi_manager %(levelname)s: %(message)s")
    )
    logger.addHandler(_h)
logger.setLevel(logging.INFO)
logger.propagate = False

# Where the boot script caches a scan taken while wlan0 is still free, so the portal can
# serve a network list even when a live rescan is unavailable in AP mode (task 3.3 / 4.2).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
LAST_SCAN_CACHE = _PROJECT_ROOT / "wifi_setup" / ".last_scan.json"

# The band the setup AP uses, matching wifi_ap.yaml usage in the boot script.
AP_BAND = "bg"

# --- Handover / verification tuning (task 4.1). ---
# How long the `nmcli device wifi connect` subprocess is given before we stop blocking on
# it. A timeout here is NOT treated as failure — the association may still land — so we
# fall through to a grace-period verify poll.
CONNECT_TIMEOUT_S = 45
# Bounded wait for wlan0 to reach `disconnected` after we release the setup AP, so the
# association is attempted against a free radio rather than one still in AP mode.
_DISCONNECT_TIMEOUT_S = 10
# Grace period after the connect subprocess returns (success, non-zero, or timeout) during
# which we keep polling _verify_association before deciding the outcome.
_VERIFY_GRACE_S = 30
_HANDOVER_POLL_INTERVAL_S = 1.0
_WLAN_IFACE = "wlan0"


def is_connected() -> bool:
    """Return True if NM reports full or limited internet connectivity."""
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "CONNECTIVITY", "general"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        state = result.stdout.strip().lower()
        return state in ("full", "limited")
    except Exception:
        return False


def _parse_scan_output(stdout: str) -> list[dict]:
    """Parse ``nmcli ... device wifi list`` output into the sorted network list.

    Preservation 3.6 — this is the parsing body exactly as ``scan_networks()`` used it
    before: ``rsplit(":", 2)`` so colon-containing SSIDs keep their colons while SIGNAL and
    SECURITY (always the last two fields) split off cleanly; blank SSIDs, the setup AP
    (``AP_SSID``), and duplicates are excluded; and the result is ordered by descending
    signal. Only the surrounding wrapper (return shape, rescan-failure handling) changes.
    """
    networks: list[dict] = []
    seen: set[str] = set()

    for line in stdout.strip().splitlines():
        # rsplit from the right: SIGNAL and SECURITY are always the last two fields.
        # This correctly handles SSIDs that contain colons.
        parts = line.rsplit(":", 2)
        if len(parts) != 3:
            continue
        ssid, signal_str, security = parts
        ssid = ssid.strip()
        if not ssid or ssid == AP_SSID or ssid in seen:
            continue
        seen.add(ssid)
        try:
            signal = int(signal_str)
        except ValueError:
            signal = 0
        networks.append(
            {
                "ssid": ssid,
                "signal": signal,
                "secured": security.strip() not in ("", "--"),
            }
        )

    return sorted(networks, key=lambda n: -n["signal"])


def _cached_networks() -> list[dict]:
    """Return the cached ``networks`` list from ``LAST_SCAN_CACHE``, or ``[]`` if unusable.

    The cache is written by ``scan_and_cache()`` (task 3.3) while wlan0 is still free.
    Tolerant of a missing/corrupt file — the caller decides how to surface that.
    """
    try:
        payload = json.loads(LAST_SCAN_CACHE.read_text())
    except (OSError, ValueError):
        return []
    networks = payload.get("networks", []) if isinstance(payload, dict) else []
    return networks if isinstance(networks, list) else []


def scan_networks() -> dict:
    """Scan for visible WiFi networks, reporting staleness instead of swallowing failures.

    Returns ``{"networks": [...], "stale": bool, "error": str | None}`` (task 4.2). The
    ``nmcli device wifi rescan`` cannot be serviced while wlan0 is hosting the setup AP, so
    that failure is EXPECTED there and must not be discarded: on a failed/errored rescan we
    fall back to the cached list from ``LAST_SCAN_CACHE`` and mark ``stale: True`` with a
    short ``error``. When the rescan and list succeed we parse as before and return
    ``stale: False, error: None``.

    Parsing (Preservation 3.6) is unchanged — see ``_parse_scan_output``.
    """
    # (1) Live rescan — its success/failure is a separate concern from parsing the list.
    rescan_ok = False
    rescan_error: str | None = None
    try:
        rescan = subprocess.run(
            ["nmcli", "device", "wifi", "rescan"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if rescan.returncode == 0:
            rescan_ok = True
        else:
            rescan_error = (rescan.stderr or rescan.stdout or "").strip() or (
                "nmcli device wifi rescan exited %d" % rescan.returncode
            )
    except Exception as exc:
        rescan_error = str(exc)

    if not rescan_ok:
        # Expected while hosting the AP: serve the cached list rather than an empty one.
        cached = _cached_networks()
        error = (
            "live rescan unavailable (AP mode); showing cached results"
            if cached
            else "live rescan unavailable (AP mode) and no cached results available"
        )
        return {"networks": cached, "stale": True, "error": error}

    # (2) Rescan succeeded — give NM a moment, then list and parse the fresh results.
    time.sleep(2)
    try:
        result = subprocess.run(
            [
                "nmcli",
                "--escape",
                "no",
                "-t",
                "-f",
                "SSID,SIGNAL,SECURITY",
                "device",
                "wifi",
                "list",
                "--rescan",
                "no",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        cached = _cached_networks()
        return {
            "networks": cached,
            "stale": True,
            "error": (
                "network list unavailable (%s); showing cached results" % exc
                if cached
                else "network list unavailable (%s) and no cached results available"
                % exc
            ),
        }

    return {
        "networks": _parse_scan_output(result.stdout),
        "stale": False,
        "error": None,
    }


def _wlan0_device_status() -> tuple[str | None, str | None]:
    """Return (state, connection) for wlan0 from ``nmcli device status`` (read-only).

    Reuses the DEVICE:STATE:CONNECTION split pattern from ``wifi_state.py``: the
    connection name (an SSID/profile) may contain colons, so split off the first two
    fields from the left and keep the remainder intact. ``state`` is returned lower-cased;
    ``connection`` is returned as NetworkManager reports it. Returns ``(None, None)`` when
    wlan0 is not listed or nmcli is unavailable.
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
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        device, state, connection = parts
        if device == _WLAN_IFACE:
            return state.strip().lower(), connection.strip()
    return None, None


def _wlan0_state() -> str | None:
    """wlan0's current NM device state, lower-cased (read-only)."""
    return _wlan0_device_status()[0]


def _wlan0_active_connection() -> str | None:
    """The connection/profile name currently active on wlan0 (read-only, as reported)."""
    return _wlan0_device_status()[1]


def _verify_association(ssid: str) -> bool:
    """True when wlan0 itself reports it has joined the requested client network.

    Association is judged by wlan0's OWN device state and active connection — NOT by
    global NM connectivity. On an ethernet-equipped device the global CONNECTIVITY value
    reflects eth0, so it is a false signal for "did wlan0 join?"; a freshly-joined wifi
    network can also briefly report ``limited``/``none`` while association is already
    correct. The real source of truth is:
      * wlan0's device state is ``connected``;
      * the active connection/profile on wlan0 equals the requested ``ssid`` AND is not the
        setup AP profile (``AP_CON_NAME``) — an SSID mismatch or the AP profile is rejected.
    ``is_connected()`` (global connectivity) is logged for context only; it is NOT a gate.
    """
    state, connection = _wlan0_device_status()
    global_conn = is_connected()

    if state != "connected":
        logger.info(
            "verify: not yet connected — wlan0 state=%r connection=%r "
            "(requested ssid=%r, global_connectivity=%s)",
            state,
            connection,
            ssid,
            global_conn,
        )
        return False
    if not connection or connection == AP_CON_NAME:
        logger.info(
            "verify: wlan0 connected but on AP/empty profile — connection=%r "
            "(requested ssid=%r)",
            connection,
            ssid,
        )
        return False
    if connection != ssid:
        # Do NOT loosen the check — just make an NM-named-profile mismatch visible.
        logger.warning(
            "verify: wlan0 connection name %r != requested ssid %r "
            "(NM may have named the profile differently); rejecting",
            connection,
            ssid,
        )
        return False

    logger.info(
        "verify: associated — wlan0 state=connected connection=%r matches requested "
        "ssid (global_connectivity=%s, informational only)",
        connection,
        global_conn,
    )
    return True


def _poll_verify(ssid: str, timeout_s: float) -> bool:
    """Poll ``_verify_association(ssid)`` up to ``timeout_s``; True on first success.

    Logs the observed wlan0 (state, connection) and global connectivity roughly once per
    second so the grace-period handover is fully traceable in the journal. Each underlying
    ``_verify_association`` call also logs the specific reason it is not yet verified.
    """
    logger.info("verify poll: starting up to %.0fs for ssid=%r", timeout_s, ssid)
    deadline = time.monotonic() + timeout_s
    attempt = 0
    while True:
        attempt += 1
        state, connection = _wlan0_device_status()
        logger.info(
            "verify poll #%d: observed wlan0 state=%r connection=%r "
            "global_connectivity=%s (requested ssid=%r)",
            attempt,
            state,
            connection,
            is_connected(),
            ssid,
        )
        if _verify_association(ssid):
            logger.info("verify poll: verified on attempt #%d", attempt)
            return True
        if time.monotonic() >= deadline:
            logger.warning(
                "verify poll: grace period elapsed after %d attempts without "
                "verifying association to ssid=%r",
                attempt,
                ssid,
            )
            return False
        time.sleep(_HANDOVER_POLL_INTERVAL_S)


def _wait_for_wlan0_disconnected(timeout_s: float) -> bool:
    """Poll until wlan0 reports ``disconnected`` (radio free), bounded by ``timeout_s``."""
    deadline = time.monotonic() + timeout_s
    while True:
        if _wlan0_state() == "disconnected":
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(_HANDOVER_POLL_INTERVAL_S)


def _wait_for_ssid_visible(ssid: str, timeout_s: float) -> bool:
    """Poll NM's scan list until ``ssid`` is visible, bounded by ``timeout_s``.

    Read-only. Lists SSIDs with ``nmcli --escape no -t -f SSID device wifi list --rescan no``
    (no colon-splitting needed for a plain membership check — each line IS the SSID) and
    compares each line exactly to ``ssid``. Returns True on the first sighting, False if the
    deadline passes. Logs found/not-found so the handover is traceable.
    """
    deadline = time.monotonic() + timeout_s
    attempt = 0
    while True:
        attempt += 1
        found = False
        try:
            result = subprocess.run(
                [
                    "nmcli",
                    "--escape",
                    "no",
                    "-t",
                    "-f",
                    "SSID",
                    "device",
                    "wifi",
                    "list",
                    "--rescan",
                    "no",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in result.stdout.splitlines():
                if line == ssid:
                    found = True
                    break
        except Exception as exc:
            logger.warning(
                "connect_to_network: ssid-visibility list raised %r (attempt #%d)",
                exc,
                attempt,
            )
        if found:
            logger.info(
                "connect_to_network: target ssid=%r visible in scan list (attempt #%d)",
                ssid,
                attempt,
            )
            return True
        if time.monotonic() >= deadline:
            logger.warning(
                "connect_to_network: target ssid=%r NOT visible in scan list after "
                "%d attempts / %.0fs (attempting connect anyway)",
                ssid,
                attempt,
                timeout_s,
            )
            return False
        time.sleep(_HANDOVER_POLL_INTERVAL_S)


def _demote_hotspot_profile() -> None:
    """Re-assert the setup AP is gone: make any surviving instance non-autoconnecting.

    ``stop_hotspot()`` deletes ``AP_CON_NAME`` up front, but if a copy survives (e.g. NM
    recreated it) we set ``connection.autoconnect no`` so it can never bring wlan0 back up
    as the setup AP on the next boot. Tolerant if the profile does not exist.
    """
    try:
        subprocess.run(
            [
                "nmcli",
                "connection",
                "modify",
                AP_CON_NAME,
                "connection.autoconnect",
                "no",
            ],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        pass


def _profile_exists(ssid: str) -> bool:
    """True when a saved NM connection profile named EXACTLY ``ssid`` exists.

    Lists profile names with ``nmcli -t -f NAME connection show`` and compares each line
    exactly to ``ssid`` (profile names may contain colons, but the ``-t -f NAME`` output is
    a single field per line, so no splitting is needed). Read-only; tolerant of failure —
    returns False if nmcli is unavailable, which routes callers to the explicit create path.
    """
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME", "connection", "show"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        logger.warning("_activate_network: listing profiles raised %r", exc)
        return False
    for line in result.stdout.splitlines():
        if line == ssid:
            return True
    return False


def _activate_network(ssid: str, password: str | None) -> tuple[int, str, str]:
    """Deterministically associate wlan0 with ``ssid`` and return (rc, stdout, stderr).

    Replaces the flaky ``nmcli device wifi connect <ssid> [password <pw>]`` path, which
    collided with a pre-existing saved profile and built an incomplete security config,
    failing with ``802-11-wireless-security.key-mgmt: property is missing``. Instead we drive
    NetworkManager profiles explicitly so the security type is never left to inference:

      * If a profile named exactly ``ssid`` EXISTS:
          - secured (password truthy): update its stored secret first with
            ``connection modify <ssid> wifi-sec.key-mgmt wpa-psk wifi-sec.psk <password>`` so
            the saved PSK matches what the user just typed (harmless if unchanged), then
            ``connection up <ssid>``.
          - open (no password): just ``connection up <ssid>`` — leave security untouched.
      * If NO profile exists, create one named exactly ``ssid`` (so ``_verify_association``'s
        wlan0-active-connection == ssid check keeps working):
          - secured: ``connection add type wifi con-name <ssid> ifname wlan0 ssid <ssid> --
            wifi-sec.key-mgmt wpa-psk wifi-sec.psk <password>``; on add failure return its
            rc/err, otherwise ``connection up <ssid>``.
          - open: ``connection add type wifi con-name <ssid> ifname wlan0 ssid <ssid>`` then
            ``connection up <ssid>``.

    The final ``connection up`` result (or an earlier add/modify failure) is returned as
    (rc, stdout, stderr). ``subprocess.TimeoutExpired`` is allowed to propagate so the caller
    handles timeout vs. clear_error exactly as before. The password VALUE is never logged —
    argv is logged with the psk masked as ``***`` and only ``bool(password)`` is reported.
    """
    exists = _profile_exists(ssid)
    logger.info(
        "_activate_network: ssid=%r password_provided=%s profile_exists=%s",
        ssid,
        bool(password),
        exists,
    )

    if exists:
        if password:
            modify_cmd = [
                "nmcli",
                "connection",
                "modify",
                ssid,
                "wifi-sec.key-mgmt",
                "wpa-psk",
                "wifi-sec.psk",
                password,
            ]
            logged_modify = [
                "nmcli",
                "connection",
                "modify",
                ssid,
                "wifi-sec.key-mgmt",
                "wpa-psk",
                "wifi-sec.psk",
                "***",
            ]
            logger.info(
                "_activate_network: updating existing profile secret argv=%r "
                "(password_provided=%s)",
                logged_modify,
                bool(password),
            )
            modify = subprocess.run(
                modify_cmd, capture_output=True, text=True, timeout=15
            )
            logger.info(
                "_activate_network: modify rc=%s stdout=%r stderr=%r",
                modify.returncode,
                (modify.stdout or "").strip(),
                (modify.stderr or "").strip(),
            )
            if modify.returncode != 0:
                return (
                    modify.returncode,
                    modify.stdout or "",
                    modify.stderr or "",
                )
        else:
            logger.info(
                "_activate_network: existing OPEN profile — bringing up without "
                "modifying security (ssid=%r)",
                ssid,
            )
    else:
        if password:
            add_cmd = [
                "nmcli",
                "connection",
                "add",
                "type",
                "wifi",
                "con-name",
                ssid,
                "ifname",
                _WLAN_IFACE,
                "ssid",
                ssid,
                "--",
                "wifi-sec.key-mgmt",
                "wpa-psk",
                "wifi-sec.psk",
                password,
            ]
            logged_add = [
                "nmcli",
                "connection",
                "add",
                "type",
                "wifi",
                "con-name",
                ssid,
                "ifname",
                _WLAN_IFACE,
                "ssid",
                ssid,
                "--",
                "wifi-sec.key-mgmt",
                "wpa-psk",
                "wifi-sec.psk",
                "***",
            ]
        else:
            add_cmd = [
                "nmcli",
                "connection",
                "add",
                "type",
                "wifi",
                "con-name",
                ssid,
                "ifname",
                _WLAN_IFACE,
                "ssid",
                ssid,
            ]
            logged_add = list(add_cmd)
        logger.info(
            "_activate_network: creating profile argv=%r (password_provided=%s)",
            logged_add,
            bool(password),
        )
        add = subprocess.run(add_cmd, capture_output=True, text=True, timeout=15)
        logger.info(
            "_activate_network: add rc=%s stdout=%r stderr=%r",
            add.returncode,
            (add.stdout or "").strip(),
            (add.stderr or "").strip(),
        )
        if add.returncode != 0:
            return (add.returncode, add.stdout or "", add.stderr or "")

    up_cmd = ["nmcli", "connection", "up", ssid]
    logger.info("_activate_network: activating argv=%r", up_cmd)
    up = subprocess.run(
        up_cmd, capture_output=True, text=True, timeout=CONNECT_TIMEOUT_S
    )
    logger.info(
        "_activate_network: up rc=%s stdout=%r stderr=%r",
        up.returncode,
        (up.stdout or "").strip(),
        (up.stderr or "").strip(),
    )
    return (up.returncode, up.stdout or "", up.stderr or "")


def connect_to_network(ssid: str, password: str | None) -> dict:
    """Sequence the radio handover and gate success on verified association.

    Ordered handover (task 4.1): the setup AP owns wlan0 when the user submits credentials,
    so we (1) note whether the AP is the active connection, (2) ``stop_hotspot()`` to delete
    the ``NuggiesHotspot`` profile — this is its first real caller — (3) disconnect wlan0 and
    poll until it reports ``disconnected`` so the radio is free, and only THEN (4) run
    ``nmcli device wifi connect`` with the existing timeout. Open networks are preserved:
    ``password=None`` simply omits the ``password`` argument (Preservation 3.7).

    A timeout is no longer automatically a failure. After the connect subprocess returns —
    whether it exited 0, non-zero, or timed out — we poll ``_verify_association(ssid)`` for a
    bounded grace period before deciding the outcome.

    Outcome mapping (returned as ``state``), decided AFTER the grace-period poll:
      * ``connected_verified`` — ``_verify_association`` became True within the grace period.
        This is the ONLY path that writes ``.wifi_configured`` (via ``mark_configured()``) and
        re-asserts the AP profile is gone. It holds regardless of the subprocess exit code, so
        a slow association that lands after the 45s timeout still ends configured.
      * ``failed`` — the connect subprocess gave a CLEAR error (non-zero exit or an exception
        such as a bad password) AND verification is still False after the grace period. We can
        observe the outcome and it is negative, so we restore the portal with ``start_hotspot()``
        for retry and carry the nmcli stderr (FAILED_WITH_REASON).
      * ``unknown_verify`` — we genuinely cannot tell: the connect subprocess timed out (no exit
        code to trust) AND verification neither confirmed nor is a clear error we can attribute,
        i.e. the radio may have moved and we lost the ability to observe the result. We do NOT
        write the marker and do NOT restore the portal (the association may in fact be up); the
        client is told to verify. Requirement 2.3 / 2.4: an unobservable outcome is reported as
        unknown, not collapsed into success or failure.
    """
    ap_was_active = _wlan0_active_connection() == AP_CON_NAME
    # NEVER log the password value — only whether one was provided.
    logger.info(
        "connect_to_network: requested ssid=%r password_provided=%s ap_was_active=%s",
        ssid,
        bool(password),
        ap_was_active,
    )

    # (2) Tear down the setup AP profile so it cannot contend for wlan0 or reappear.
    stop_hotspot()
    logger.info("connect_to_network: stopped hotspot")

    # (3) Release wlan0 and wait for it to actually reach `disconnected` before associating.
    try:
        disconnect_result = subprocess.run(
            ["nmcli", "device", "disconnect", _WLAN_IFACE],
            capture_output=True,
            text=True,
            timeout=15,
        )
        logger.info(
            "connect_to_network: disconnect wlan0 rc=%s stderr=%r",
            disconnect_result.returncode,
            (disconnect_result.stderr or "").strip(),
        )
    except Exception as exc:
        # A disconnect failure is not fatal on its own — wlan0 may already be free (e.g. the
        # AP teardown released it). Fall through to the bounded poll, which is the real gate.
        logger.warning("connect_to_network: disconnect wlan0 raised %r", exc)
    disconnected = _wait_for_wlan0_disconnected(_DISCONNECT_TIMEOUT_S)
    logger.info(
        "connect_to_network: wlan0 reached disconnected in time=%s", disconnected
    )

    # (3b) Rescan the freed radio so NM has a fresh scan entry for the target network.
    # After releasing wlan0 from AP mode, NM needs a current scan of the target network to
    # infer its security type (WPA-PSK); without it, `device wifi connect` fails with
    # "802-11-wireless-security.key-mgmt: property is missing" even when a password is
    # supplied. This is additive — we proceed to connect regardless of the rescan result.
    try:
        rescan_result = subprocess.run(
            ["nmcli", "device", "wifi", "rescan", "ifname", _WLAN_IFACE],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if rescan_result.returncode == 0:
            logger.info("connect_to_network: pre-connect rescan rc=0")
        else:
            logger.warning(
                "connect_to_network: pre-connect rescan rc=%s stderr=%r "
                "(continuing — a stale scan may still let NM infer security)",
                rescan_result.returncode,
                (rescan_result.stderr or rescan_result.stdout or "").strip(),
            )
    except Exception as exc:
        logger.warning(
            "connect_to_network: pre-connect rescan raised %r (continuing)", exc
        )
    # Give the target a chance to appear in NM's scan list before we attempt to join it.
    _wait_for_ssid_visible(ssid, 10)

    # (4) Only now attempt the client association against a free radio, using a
    # deterministic profile-based helper instead of the flaky `device wifi connect` path
    # that collided with a pre-existing profile and left the security config incomplete.
    logger.info(
        "connect_to_network: associating via _activate_network (password_provided=%s)",
        bool(password),
    )

    timed_out = False
    clear_error: str | None = None
    try:
        rc, out, err = _activate_network(ssid, password)
        logger.info(
            "connect_to_network: association rc=%s stdout=%r stderr=%r",
            rc,
            (out or "").strip(),
            (err or "").strip(),
        )
        if rc != 0:
            clear_error = (err or out).strip() or "Connection failed."
    except subprocess.TimeoutExpired:
        # The association may still be completing — do NOT call this a failure yet.
        timed_out = True
        logger.warning(
            "connect_to_network: association subprocess timed out after %ss "
            "(association may still be completing)",
            CONNECT_TIMEOUT_S,
        )
    except Exception as exc:
        clear_error = str(exc)
        logger.warning("connect_to_network: association subprocess raised %r", exc)

    # (5) Grace-period verification poll — the single arbiter of the outcome.
    verified = _poll_verify(ssid, _VERIFY_GRACE_S)
    logger.info("connect_to_network: final verified=%s", verified)

    if verified:
        # (7) Only after successful verification: write the marker and re-assert the AP is
        # gone (non-autoconnecting), so the joined network is the only wlan0 candidate.
        mark_configured()
        _demote_hotspot_profile()
        logger.info(
            "connect_to_network: decision=connected_verified ssid=%r "
            "(marker written, hotspot profile demoted)",
            ssid,
        )
        return {
            "state": "connected_verified",
            "ssid": ssid,
            "message": "Connected successfully.",
        }

    if clear_error is not None:
        # (8) Observable, negative outcome: restore the portal so the user can retry.
        start_hotspot()
        logger.warning(
            "connect_to_network: decision=failed ssid=%r message=%r "
            "(portal restored for retry)",
            ssid,
            clear_error,
        )
        return {
            "state": "failed",
            "ssid": ssid,
            "message": clear_error,
        }

    # Timed out (or otherwise no clear error) and verification could neither confirm nor
    # refute — we genuinely cannot observe the result. Report unknown; leave the radio as
    # NM left it (the association may yet land) and do not write the marker.
    _ = (
        timed_out,
        ap_was_active,
    )  # documented signals; behaviour above does not branch on them
    unknown_message = (
        "Connection outcome could not be confirmed — please re-check whether the "
        "device joined the network."
    )
    logger.warning(
        "connect_to_network: decision=unknown_verify ssid=%r timed_out=%s "
        "(marker NOT written, portal left as-is) message=%r",
        ssid,
        timed_out,
        unknown_message,
    )
    return {
        "state": "unknown_verify",
        "ssid": ssid,
        "message": unknown_message,
    }


def hotspot_argv(password: str = AP_PASSWORD, band: str = AP_BAND) -> list[str]:
    """Build the nmcli argv that starts the setup AP.

    This is the single source of truth for the hotspot invocation, shared by both the
    Python caller (``start_hotspot``) and the boot script, which now delegates here
    instead of duplicating the command. Values come from ``wifi_ap.yaml`` (via
    ``ap_config``), never baked-in literals, so the AP is password-protected on band
    ``bg`` exactly as the boot script produced it before.
    """
    return [
        "nmcli",
        "device",
        "wifi",
        "hotspot",
        "ifname",
        "wlan0",
        "ssid",
        AP_SSID,
        "con-name",
        AP_CON_NAME,
        "password",
        password,
        "band",
        band,
    ]


def start_hotspot(password: str = AP_PASSWORD, band: str = AP_BAND) -> bool:
    """Start the NuggiesSetup WPA-protected AP via NetworkManager.

    The single hotspot implementation for every caller. Uses the ``wifi_ap.yaml``
    password and band ``bg`` by default, matching the invocation the boot script issued
    before it began delegating here.
    """
    try:
        result = subprocess.run(
            hotspot_argv(password=password, band=band),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def stop_hotspot() -> None:
    subprocess.run(
        ["nmcli", "connection", "delete", AP_CON_NAME],
        capture_output=True,
        timeout=10,
    )


def scan_and_cache() -> int:
    """Scan for networks and cache the result to ``LAST_SCAN_CACHE``.

    Called from the boot script while wlan0 is still free (before the AP takes over the
    radio), so the captive portal has a network list to serve when a live rescan is not
    possible in AP mode. Writes a JSON object with a ``networks`` list and a ``scanned_at``
    timestamp; the shape stays resilient to the task 4.2 change to ``scan_networks()``.

    When running as root, the cache file is chowned to the project-root owner so the ``pi``
    API can maintain/read it later, matching the resolver's marker-ownership strategy.
    """
    result = scan_networks()
    # scan_networks() returns a list today; task 4.2 will make it a dict with a "networks"
    # key. Accept either so this step does not break across that change.
    if isinstance(result, dict):
        networks = result.get("networks", [])
    else:
        networks = result

    payload = {"networks": networks, "scanned_at": time.time()}

    LAST_SCAN_CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LAST_SCAN_CACHE.with_suffix(LAST_SCAN_CACHE.suffix + ".tmp")
    tmp.write_text(json.dumps(payload))
    os.replace(str(tmp), str(LAST_SCAN_CACHE))

    if os.geteuid() == 0:
        try:
            st = _PROJECT_ROOT.stat()
            os.chown(str(LAST_SCAN_CACHE), st.st_uid, st.st_gid)
        except OSError:
            pass

    return len(networks)


# --------------------------------------------------------------------------- #
# CLI — lets the boot script start the real AP and lets an operator dry-run the
# argv without touching the radio.
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wifi_setup.wifi_manager",
        description="Manage the Nuggies setup hotspot.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--print-hotspot-argv",
        action="store_true",
        help="Print the nmcli argv start_hotspot() would run, then exit (dry run, does "
        "not execute nmcli).",
    )
    group.add_argument(
        "--start-hotspot",
        action="store_true",
        help="Actually start the setup AP (runs the nmcli hotspot command). Intended for "
        "the root boot service.",
    )
    group.add_argument(
        "--scan-cache",
        action="store_true",
        help="Scan for networks while wlan0 is free and cache the result to "
        ".last_scan.json for the portal to serve. Intended for the root boot service, "
        "run before --start-hotspot.",
    )
    args = parser.parse_args(argv)

    if args.print_hotspot_argv:
        print(" ".join(hotspot_argv()))
        return 0

    if args.start_hotspot:
        return 0 if start_hotspot() else 1

    if args.scan_cache:
        count = scan_and_cache()
        print(f"cached {count} networks to {LAST_SCAN_CACHE}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
