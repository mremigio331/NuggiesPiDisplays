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


def reset_settings() -> None:
    """Overwrite settings.json with the factory defaults."""
    with FileLock(_LOCK_PATH):
        shutil.copy(_DEFAULTS_PATH, _SETTINGS_PATH)


def read_section(key: str) -> dict:
    return read_settings().get(key, {})


def write_section(key: str, section: dict) -> None:
    settings = read_settings()
    settings[key] = section
    write_settings(settings)


# --- Update stage ----------------------------------------------------------- #
# Which release tag this device tracks: "beta" (gets each build immediately) or
# "prod" (gets only builds you approved). Default "prod". setup.sh reads the
# same key to decide which git tag to pull, so UI and updater always agree.
VALID_UPDATE_STAGES = ("beta", "prod")


def read_update_stage() -> str:
    try:
        stage = str(read_settings().get("update_stage", "prod")).strip().lower()
    except Exception:
        return "prod"
    return stage if stage in VALID_UPDATE_STAGES else "prod"


def write_update_stage(stage: str) -> str:
    stage = str(stage).strip().lower()
    if stage not in VALID_UPDATE_STAGES:
        raise ValueError(
            f"update_stage must be one of {VALID_UPDATE_STAGES}, got {stage!r}"
        )
    settings = read_settings()
    settings["update_stage"] = stage
    write_settings(settings)
    return stage


# --- Display overlay -------------------------------------------------------- #
# A transient full-screen message any display mode renders over its normal
# content, driven entirely through settings so it uses the display's existing
# ~1s settings poll (no new transport). Written by the button handler during a
# both-button factory-reset hold; read by the display render loop.
#   None                     -> no overlay (normal rendering)
#   {"kind": "reset_prompt",      -> "Hold Ns for Factory Reset" countdown
#    "seconds_left": int}
#   {"kind": "reset_running"}     -> blanked screen + "Factory Reset"


def read_overlay() -> dict | None:
    return read_settings().get("overlay")


def write_overlay(overlay: dict | None) -> None:
    settings = read_settings()
    if overlay is None:
        settings.pop("overlay", None)
    else:
        settings["overlay"] = overlay
    write_settings(settings)
