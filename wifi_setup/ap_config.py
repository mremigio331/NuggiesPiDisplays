"""Shared access-point config loaded from wifi_ap.yaml at the project root."""

import socket
from pathlib import Path
import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "wifi_ap.yaml"

_cfg = yaml.safe_load(_CONFIG_PATH.read_text())


def _derive_ap_ssid() -> str:
    """Derive the visible setup-AP SSID from this device's hostname — never hardcoded.

    Rule: uppercase the FIRST character of the hostname, keep the REST unchanged, then
    append "Display" (e.g. ``stonks`` -> ``StonksDisplay``, ``nuggies`` -> ``NuggiesDisplay``).
    Note we deliberately do NOT use ``str.capitalize()`` — that would lowercase the rest,
    turning ``myPi`` into ``Mypi``. An empty hostname falls back to the yaml ``ssid`` value
    (documented default ``NuggiesDisplay``). The boot script (scripts/wifi_setup_service.sh)
    derives the same name with the identical rule so logs and the actual AP name agree.
    """
    h = socket.gethostname()
    if h:
        return f"{h[:1].upper()}{h[1:]}Display"
    return _cfg.get("ssid", "NuggiesDisplay")


AP_SSID = _derive_ap_ssid()
AP_PASSWORD = _cfg["password"]
# AP_CON_NAME stays as the yaml connection_name (NuggiesHotspot): the connection
# PROFILE name is unrelated to the visible SSID and other code matches on it.
AP_CON_NAME = _cfg["connection_name"]
AP_IP = _cfg["ap_ip"]
