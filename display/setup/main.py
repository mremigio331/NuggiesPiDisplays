#!/usr/bin/env python3
import sys
from pathlib import Path
import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Appended (not inserted) so ``display`` still resolves to display/setup/display.py.
sys.path.append(str(_PROJECT_ROOT))

from display import run  # noqa: E402
from wifi_setup.ap_config import AP_SSID  # noqa: E402

_cfg = yaml.safe_load((_PROJECT_ROOT / "wifi_ap.yaml").read_text())

if __name__ == "__main__":
    # AP_SSID is the real, per-device setup network name (Nuggies-<last 4 MAC>).
    run(ssid=AP_SSID, password=_cfg["password"])
