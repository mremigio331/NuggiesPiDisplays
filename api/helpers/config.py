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


# --- Display schedule ------------------------------------------------------- #
# Time-of-day automation: at each "time" (device-local HH:MM, 24h) the display
# switches to "mode". The scheduler loop (helpers/schedule.py) applies the rule
# whose time is the latest one at or before the current local time, so one rule
# stays active until the next rule time arrives, wrapping at midnight.
#
# Timezone is ALWAYS the device's own local time (the Pi ships worldwide and is
# provisioned to its owner's zone), so no timezone is stored here.
#
# A MANUAL switch (web UI, button, or /system/display) after the schedule has
# taken over turns the schedule OFF (enabled=false) until the user re-enables
# it. The scheduler detects this by comparing active_display against the mode it
# last set itself; see helpers/schedule.py.
#
# Shape:
#   { "enabled": bool, "rules": [ { "time": "HH:MM", "mode": <display mode> } ] }
import re as _re

from constants import DISPLAY_MODES as _DISPLAY_MODES

_TIME_RE = _re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def schedule_mode_options() -> dict:
    """Map of display mode -> [{key,label}] of its schedule sub-options.

    Each mode's options come from that mode's OWN module (its source of truth),
    so a league added to the sports dicts shows up here with no second edit.
    Imported lazily because those modules import this one. A mode with no
    sub-option is simply absent from the map.
    """
    options: dict[str, list[dict]] = {}
    try:
        from endpoints.sports.update_settings import sport_options

        options["sports"] = sport_options()
    except Exception:
        # Never let a sub-module import problem break schedule loading.
        pass
    return options


def normalize_schedule(raw: dict | None) -> dict:
    """Coerce an on-disk schedule block into the canonical shape.

    Tolerates missing keys and old settings files that predate the feature
    (a user device upgrading keeps its other settings and gains a disabled,
    empty schedule). Invalid rules are dropped rather than raising, so one bad
    row can never stop the whole schedule from loading. Rules are returned
    sorted by time.
    """
    raw = raw if isinstance(raw, dict) else {}
    rules: list[dict] = []
    for r in raw.get("rules", []) or []:
        if not isinstance(r, dict):
            continue
        t = str(r.get("time", "")).strip()
        if not _TIME_RE.match(t):
            continue

        # Action kind. Default "mode" so a legacy rule saved before actions
        # existed (just {time, mode[, option]}) still loads and behaves the same.
        action = str(r.get("action", "mode")).strip().lower() or "mode"

        if action == "mode":
            mode = str(r.get("mode", "")).strip()
            if mode not in _DISPLAY_MODES:
                continue
            rule = {"time": t, "action": "mode", "mode": mode}
            # Optional per-mode sub-option (e.g. sports league), validated
            # against the mode's own whitelist; unknown/absent is dropped.
            valid_opts = {o["key"] for o in schedule_mode_options().get(mode, [])}
            opt = str(r.get("option", "")).strip()
            if opt and opt in valid_opts:
                rule["option"] = opt

        elif action == "power":
            power = str(r.get("power", "")).strip().lower()
            if power not in ("on", "off"):
                continue
            rule = {"time": t, "action": "power", "power": power}

        elif action == "brightness":
            # Accept a raw 1-100 value. Clamp into range; an unparseable value
            # drops the rule rather than raising.
            try:
                val = int(r.get("brightness"))
            except (TypeError, ValueError):
                continue
            val = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, val))
            rule = {"time": t, "action": "brightness", "brightness": val}

        else:
            # Unknown action — drop it rather than guess.
            continue

        rules.append(rule)

    # Sort by time, then dedupe on time keeping the last-wins entry so a single
    # minute never maps to two actions.
    rules.sort(key=lambda r: r["time"])
    deduped: dict[str, dict] = {}
    for r in rules:
        deduped[r["time"]] = r
    rules = [deduped[t] for t in sorted(deduped)]
    return {"enabled": bool(raw.get("enabled", False)), "rules": rules}


def read_schedule() -> dict:
    return normalize_schedule(read_settings().get("schedule"))


def write_schedule(schedule: dict) -> dict:
    """Validate + persist the schedule block. Returns the normalized value."""
    normalized = normalize_schedule(schedule)
    settings = read_settings()
    settings["schedule"] = normalized
    write_settings(settings)
    return normalized
