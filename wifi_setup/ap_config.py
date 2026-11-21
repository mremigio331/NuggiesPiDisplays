"""Shared access-point config loaded from wifi_ap.yaml at the project root."""

from pathlib import Path
import yaml

from .device_name import setup_ssid

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "wifi_ap.yaml"

_cfg = yaml.safe_load(_CONFIG_PATH.read_text())


def _derive_ap_ssid() -> str:
    """Setup-AP SSID: ``Nuggies-<last 4 MAC hex>`` (e.g. Nuggies-A1B2).

    The MAC tail makes the name unique per device, so several displays in one home never
    advertise the same setup network. See wifi_setup/device_name.py. The boot script
    scripts/wifi_setup_service.sh gets the same suffix from that module.
    """
    return setup_ssid()


AP_SSID = _derive_ap_ssid()
AP_PASSWORD = _cfg["password"]
# AP_CON_NAME stays as the yaml connection_name (NuggiesHotspot): the connection
# PROFILE name is unrelated to the visible SSID and other code matches on it.
AP_CON_NAME = _cfg["connection_name"]
AP_IP = _cfg["ap_ip"]
