"""AP credentials loaded from wifi_ap.yaml at the project root."""

import yaml
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_cfg = yaml.safe_load((_PROJECT_ROOT / "wifi_ap.yaml").read_text())

AP_SSID = _cfg["ssid"]
AP_PASSWORD = _cfg["password"]
AP_CON_NAME = _cfg["connection_name"]
AP_IP = _cfg["ap_ip"]
