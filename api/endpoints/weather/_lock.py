"""Weather screen lock: pins the matrix to one screen for LOCK_TTL.

The lock is stored in the weather settings as
    locked_view:  "current" | "hourly" | "forecast" | "sky"   ("" = unlocked)
    locked_until: UTC ISO timestamp, e.g. "2026-11-19T03:45:00Z"
An expired lock is dropped on read, so the display resumes its rotation on its
own without anyone having to unlock it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

LOCK_TTL = timedelta(hours=1)


def lock_expiry() -> str:
    return (datetime.now(timezone.utc) + LOCK_TTL).strftime("%Y-%m-%dT%H:%M:%SZ")


def with_active_lock(weather: dict) -> dict:
    """Return a copy of the weather settings with an expired or malformed
    lock cleared. A lock with no expiry (hand-edited) counts as expired."""
    out = dict(weather)
    if not out.get("locked_view"):
        out["locked_view"] = ""
        out.pop("locked_until", None)
        return out
    try:
        until = datetime.strptime(out.get("locked_until", ""), "%Y-%m-%dT%H:%M:%SZ")
        expired = until.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)
    except (TypeError, ValueError):
        expired = True
    if expired:
        out["locked_view"] = ""
        out.pop("locked_until", None)
    return out
