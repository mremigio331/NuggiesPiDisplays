"""Shared access-point config loaded from wifi_ap.yaml at the project root."""

from pathlib import Path
import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "wifi_ap.yaml"

_cfg = yaml.safe_load(_CONFIG_PATH.read_text())

AP_SSID = _cfg["ssid"]
AP_PASSWORD = _cfg["password"]
AP_CON_NAME = _cfg["connection_name"]
AP_IP = _cfg["ap_ip"]
