"""Weather screen lock: pins the matrix to one weather screen.

The lock is stored in the weather settings as
    locked_view:  "current" | "hourly" | "forecast" | "sky"   ("" = unlocked)
It has no time limit. It ends when the user unlocks it, or picks a display
by hand (website or button), which calls helpers.config.clear_weather_lock.
"""

from __future__ import annotations

VALID_VIEWS = ("current", "hourly", "forecast", "sky")


def with_active_lock(weather: dict) -> dict:
    """Return a copy of the weather settings with a clean lock field.

    Drops an unknown screen name, and the `locked_until` expiry that older
    builds wrote (locks no longer expire), so old on-disk settings still load.
    """
    out = dict(weather)
    out.pop("locked_until", None)
    if out.get("locked_view") not in VALID_VIEWS:
        out["locked_view"] = ""
    return out
