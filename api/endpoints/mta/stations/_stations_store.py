import json
from pathlib import Path
from filelock import FileLock

_STATIONS_FILE = Path(__file__).resolve().parents[3] / "data" / "stations_config.json"
_LOCK = Path(str(_STATIONS_FILE) + ".lock")


def load() -> dict:
    with FileLock(_LOCK):
        with open(_STATIONS_FILE) as f:
            return json.load(f)


def save(data: dict) -> None:
    with FileLock(_LOCK):
        with open(_STATIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
