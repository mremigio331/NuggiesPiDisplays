"""Per-device identity for the WiFi setup flow.

Every unconfigured device advertises ``Nuggies-<XXXX>`` and, until the user picks a
name, uses the hostname ``nuggies-<xxxx>``, where ``XXXX`` is the LAST four hex characters
of the wlan0 MAC address. The first six MAC characters are the chip maker's ID and are
identical on every Pi, so only the tail tells devices apart. Two devices in one home
therefore never share a setup WiFi name or a ``.local`` name.

CLI (run as root by scripts/wifi_setup_service.sh):
    python3 -m wifi_setup.device_name --suffix            # prints e.g. A1B2
    python3 -m wifi_setup.device_name --reset-hostname    # hostname -> nuggies-a1b2
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_MAC_PATHS = (
    Path("/sys/class/net/wlan0/address"),
    Path("/sys/class/net/eth0/address"),
)
_AVAHI_CONF = Path("/etc/avahi/avahi-daemon.conf")
_HOSTS = Path("/etc/hosts")

# RFC 1123 label: letters, digits, dashes; no leading/trailing dash; max 63.
_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def mac_suffix() -> str:
    """Last 4 hex chars of the MAC, uppercase. ``0000`` if no MAC can be read."""
    for path in _MAC_PATHS:
        try:
            digits = re.sub(r"[^0-9a-fA-F]", "", path.read_text())
        except OSError:
            continue
        if len(digits) >= 4:
            return digits[-4:].upper()
    return "0000"


def default_hostname() -> str:
    return f"nuggies-{mac_suffix().lower()}"


def setup_ssid() -> str:
    return f"Nuggies-{mac_suffix()}"


def normalize_name(raw: str | None) -> str | None:
    """Lowercase + trim the user's name; return None when it is not a valid hostname."""
    name = (raw or "").strip().lower().replace(" ", "-")
    return name if _NAME_RE.match(name) else None


def _rewrite_hosts(name: str) -> None:
    """Point the 127.0.1.1 line at the new name so ``sudo`` does not warn."""
    try:
        lines = _HOSTS.read_text().splitlines()
    except OSError:
        return
    out, found = [], False
    for line in lines:
        if line.split("#", 1)[0].split()[:1] == ["127.0.1.1"]:
            out.append(f"127.0.1.1\t{name}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"127.0.1.1\t{name}")
    tmp = _HOSTS.with_name("hosts.nuggies.tmp")
    tmp.write_text("\n".join(out) + "\n")
    tmp.replace(_HOSTS)


def _rewrite_avahi(name: str) -> None:
    """setup.sh pins avahi's host-name to the hostname; keep the pin in step."""
    try:
        text = _AVAHI_CONF.read_text()
    except OSError:
        return
    new = re.sub(r"(?m)^host-name=.*$", f"host-name={name}", text)
    if new != text:
        _AVAHI_CONF.write_text(new)


def apply_hostname(name: str) -> bool:
    """Set the system hostname and everything that mirrors it. Needs root.

    Returns True on success. Never raises: a failed rename must not block the WiFi join,
    the device just keeps its previous name.
    """
    if not _NAME_RE.match(name):
        logger.error("apply_hostname: refusing invalid name %r", name)
        return False
    try:
        subprocess.run(["hostnamectl", "set-hostname", name], check=True, timeout=15)
        _rewrite_hosts(name)
        _rewrite_avahi(name)
        subprocess.run(
            ["systemctl", "restart", "avahi-daemon"], check=False, timeout=30
        )
        logger.info("apply_hostname: hostname is now %s", name)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("apply_hostname(%s) failed: %r", name, exc)
        return False


if __name__ == "__main__":
    if "--suffix" in sys.argv:
        print(mac_suffix())
    elif "--reset-hostname" in sys.argv:
        sys.exit(0 if apply_hostname(default_hostname()) else 1)
    else:
        print(__doc__)
