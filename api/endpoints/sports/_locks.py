"""Locked-game list — shared by the sports settings and lock endpoints.

A lock pins a game to the matrix. Several games can be locked at once: the
display then cycles through just those games instead of the whole slate.

Each lock stores a UTC expiry, so reading is a single timestamp comparison with
no arithmetic — anything past `expires_at` is dropped. Expired locks disappear
from every read and are physically removed on the next settings write, so no
cleanup job is needed.

Lock entry shape:
    {
      "event_id":   "401872923",          # ESPN event id
      "sport":      "nfl",                # league it belongs to
      "locked_at":  "2026-09-13T18:20:00Z",  # informational
      "expires_at": "2026-09-14T18:20:00Z"   # dropped once now() passes this
    }
"""

from datetime import datetime, timedelta, timezone

LOCK_TTL = timedelta(hours=24)
MAX_EVENT_ID = 32


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def to_iso(moment: datetime) -> str:
    """Format as 'YYYY-MM-DDTHH:MM:SSZ'."""
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value) -> datetime | None:
    """Parse an ISO timestamp, assuming UTC when no offset is present."""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def valid_event_id(value: str) -> bool:
    """Event ids come from ESPN: short alphanumeric strings."""
    return bool(value) and value.isalnum() and len(value) <= MAX_EVENT_ID


def _expiry_of(entry: dict) -> datetime | None:
    """Expiry for a lock entry.

    Falls back to locked_at + LOCK_TTL so a hand-written entry that only has a
    lock time still behaves sensibly instead of vanishing.
    """
    expires_at = parse_iso(entry.get("expires_at"))
    if expires_at:
        return expires_at
    locked_at = parse_iso(entry.get("locked_at"))
    return locked_at + LOCK_TTL if locked_at else None


def prune(locks) -> list[dict]:
    """Return well-formed, unexpired locks, oldest first."""
    if not isinstance(locks, list):
        return []
    now = _utc_now()
    kept: list[dict] = []
    for entry in locks:
        if not isinstance(entry, dict):
            continue
        event_id = str(entry.get("event_id") or "")
        expires_at = _expiry_of(entry)
        if not valid_event_id(event_id) or expires_at is None or expires_at <= now:
            continue
        kept.append(
            {
                "event_id": event_id,
                "sport": str(entry.get("sport") or ""),
                "locked_at": entry.get("locked_at") or to_iso(now),
                "expires_at": to_iso(expires_at),
            }
        )
    return kept


def read(sports: dict) -> list[dict]:
    """Unexpired locks from a sports settings dict."""
    return prune(sports.get("locked_games"))


def write(sports: dict, locks: list[dict]) -> list[dict]:
    """Store locks, dropping the single-lock key this list replaced."""
    sports["locked_games"] = locks
    sports.pop("locked_event_id", None)
    return locks


def add(locks: list[dict], event_id: str, sport: str) -> list[dict]:
    """Add a lock, or restart the expiry window if the game is already locked."""
    now = _utc_now()
    kept = [lock for lock in locks if lock["event_id"] != event_id]
    kept.append(
        {
            "event_id": event_id,
            "sport": sport,
            "locked_at": to_iso(now),
            "expires_at": to_iso(now + LOCK_TTL),
        }
    )
    return kept


def remove(locks: list[dict], event_id: str) -> list[dict]:
    return [lock for lock in locks if lock["event_id"] != event_id]
