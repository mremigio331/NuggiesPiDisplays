#!/usr/bin/env python3
from pathlib import Path
import yaml

from display import run

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_cfg = yaml.safe_load((_PROJECT_ROOT / "wifi_ap.yaml").read_text())

if __name__ == "__main__":
    run(ssid=_cfg["ssid"], password=_cfg["password"])
