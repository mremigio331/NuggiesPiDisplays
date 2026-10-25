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


# --- Display brightness ----------------------------------------------------- #
# Universal LED brightness (0-100) applied to every display mode. The matrix
# library scales all colors by this before they reach the panel, so it dims the
# whole display uniformly. Default 100 (full). setup.sh does not read this;
# each mode's build_matrix() fetches it from the API at startup, so a change
# takes effect on the next display restart.
BRIGHTNESS_MIN = 1
BRIGHTNESS_MAX = 100
DEFAULT_BRIGHTNESS = 100
# Named presets the UI offers. The backend owns these values so UI and device
# always agree; write_display_brightness still accepts any raw 1-100 too.
BRIGHTNESS_PRESETS = {"full": 100, "medium": 60, "low": 25}


def read_display_brightness() -> int:
    try:
        val = int(read_settings().get("display_brightness", DEFAULT_BRIGHTNESS))
    except (TypeError, ValueError):
        return DEFAULT_BRIGHTNESS
    return max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, val))


def write_display_brightness(value: int) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError("display_brightness must be an integer 1-100")
    if not (BRIGHTNESS_MIN <= value <= BRIGHTNESS_MAX):
        raise ValueError(
            f"display_brightness must be {BRIGHTNESS_MIN}-{BRIGHTNESS_MAX}, got {value}"
        )
    settings = read_settings()
    settings["display_brightness"] = value
    write_settings(settings)
    return value
