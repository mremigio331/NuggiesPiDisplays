import json
from pathlib import Path

_DEV_CONFIG_PATH = Path(__file__).resolve().parents[2] / "dev_config.json"


def is_dev_mode() -> bool:
    try:
        with open(_DEV_CONFIG_PATH) as f:
            return bool(json.load(f).get("dev_mode", False))
    except Exception:
        return False
