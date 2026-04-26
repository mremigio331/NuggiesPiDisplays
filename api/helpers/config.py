import json
import shutil
from pathlib import Path
from filelock import FileLock

_API_DIR = Path(__file__).resolve().parents[1]
_SETTINGS_PATH = _API_DIR / "settings.json"
_DEFAULTS_PATH = _API_DIR / "settings.default.json"
_LOCK_PATH = Path(str(_SETTINGS_PATH) + ".lock")


def _ensure_settings() -> None:
    if not _SETTINGS_PATH.exists():
        shutil.copy(_DEFAULTS_PATH, _SETTINGS_PATH)


def read_settings() -> dict:
    _ensure_settings()
    with FileLock(_LOCK_PATH):
        with open(_SETTINGS_PATH) as f:
            return json.load(f)


def write_settings(data: dict) -> None:
    with FileLock(_LOCK_PATH):
        with open(_SETTINGS_PATH, "w") as f:
            json.dump(data, f, indent=2)


def read_section(key: str) -> dict:
    return read_settings().get(key, {})


def write_section(key: str, section: dict) -> None:
    settings = read_settings()
    settings[key] = section
    write_settings(settings)
