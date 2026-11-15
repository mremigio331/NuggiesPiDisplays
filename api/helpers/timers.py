"""Countdown timers that take over the LED panel when they end.

A timer is saved in settings["timers"] as ``{id: {label, ends_at, created_at,
fired}}``. ``ends_at`` and ``created_at`` are Unix epoch seconds, so a timer
survives reboots and does not care about time zones once it is set.

A timer is "done" once ``ends_at`` has passed. Done timers stay until someone
dismisses them (a board button tap or the website), and dismissing deletes the
entry. While any timer is done, GET /system/display-overlay serves a ``timer``
overlay for the oldest one, so every display mode shows it over its own
content. Nothing switches modes, so cycles and schedule rules keep running
underneath and the panel returns to whatever is current after the last dismiss.

The watcher is EDGE-triggered: when a timer first ends it is marked ``fired``
and, if the display is off, the display is turned on once. Turning the display
off again while the alert shows leaves it off.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timedelta

from filelock import FileLock

from helpers.config import (
    _LOCK_PATH,
    _SETTINGS_PATH,
    _ensure_settings,
    read_settings,
    text_char_allowed,
)
from helpers.process import is_running, start_display
from helpers.wifi_state import WIFI_FLAG

logger = logging.getLogger(__name__)

TIMER_MAX_COUNT = 10
TIMER_MAX_LABEL = 20
TIMER_MAX_SECONDS = 24 * 60 * 60
TIMER_DEFAULT_LABEL = "Timer"
TIMER_SNOOZE_SECONDS = 5 * 60

TICK_SECONDS = 1


def _mutate(fn):
    """Run ``fn(timers)`` on the saved timers dict and save it, under one lock.

    Read and write share a single lock hold so a button dismiss and the watcher
    marking a timer fired can't each save over the other's change.
    """
    _ensure_settings()
    with FileLock(_LOCK_PATH):
        with open(_SETTINGS_PATH) as f:
            settings = json.load(f)
        timers = settings.get("timers")
        if not isinstance(timers, dict):
            timers = {}
        result = fn(timers)
        settings["timers"] = timers
        with open(_SETTINGS_PATH, "w") as f:
            json.dump(settings, f, indent=2)
    return result


def _valid(timer) -> bool:
    return isinstance(timer, dict) and isinstance(timer.get("ends_at"), (int, float))


def list_timers(settings: dict | None = None, now: float | None = None) -> list[dict]:
    """All timers, soonest first, each with its id and a ``done`` flag."""
    settings = read_settings() if settings is None else settings
    now = time.time() if now is None else now
    raw = settings.get("timers")
    if not isinstance(raw, dict):
        return []
    timers = [
        {
            "id": tid,
            "label": str(t.get("label") or TIMER_DEFAULT_LABEL),
            "ends_at": int(t["ends_at"]),
            "created_at": int(t.get("created_at") or t["ends_at"]),
            "done": t["ends_at"] <= now,
        }
        for tid, t in raw.items()
        if _valid(t)
    ]
    return sorted(timers, key=lambda t: (t["ends_at"], t["created_at"]))


def clean_label(label: str | None) -> str:
    """Strip characters the panel fonts can't draw; blank becomes "Timer"."""
    text = "".join(ch for ch in str(label or "") if text_char_allowed(ch))
    text = " ".join(text.split())[:TIMER_MAX_LABEL].strip()
    return text or TIMER_DEFAULT_LABEL


def next_clock_time(hhmm: str, now: datetime | None = None) -> int:
    """Epoch of the next time the device clock reads ``hhmm`` (today or tomorrow).

    Uses the device's local time, the same clock the schedule rules use.
    Raises ValueError for anything that isn't a valid 24-hour ``HH:MM``.
    """
    hour, minute = (int(p) for p in hhmm.split(":"))
    now = now or datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return int(target.timestamp())


def add_timer(label: str, ends_at: int) -> dict:
    """Save a new timer. Raises ValueError when the timer limit is reached."""
    tid = uuid.uuid4().hex[:12]

    def add(timers):
        if len(timers) >= TIMER_MAX_COUNT:
            raise ValueError(f"You can have up to {TIMER_MAX_COUNT} timers")
        timers[tid] = {
            "label": label,
            "ends_at": int(ends_at),
            "created_at": int(time.time()),
            "fired": False,
        }

    _mutate(add)
    logger.info("Timer added: %r ends at %s", label, ends_at)
    return {"id": tid, "label": label, "ends_at": int(ends_at)}


def delete_timer(timer_id: str) -> bool:
    """Delete one timer (cancel or dismiss). False if it doesn't exist."""
    removed = _mutate(lambda timers: timers.pop(timer_id, None))
    if removed:
        logger.info("Timer removed: %r", removed.get("label"))
    return removed is not None


def dismiss_done() -> int:
    """Delete every done timer. Returns how many were removed."""
    now = time.time()

    def drop(timers):
        done = [tid for tid, t in timers.items() if not _valid(t) or t["ends_at"] <= now]
        for tid in done:
            timers.pop(tid)
        return len(done)

    count = _mutate(drop)
    if count:
        logger.info("Dismissed %d done timer(s)", count)
    return count


def dismiss_oldest_done() -> dict | None:
    """Delete the done timer the panel is showing (the oldest). Board buttons use this."""
    now = time.time()

    def drop(timers):
        done = [(t["ends_at"], tid) for tid, t in timers.items() if _valid(t) and t["ends_at"] <= now]
        if not done:
            return None
        return timers.pop(min(done)[1])

    removed = _mutate(drop)
    if removed:
        logger.info("Timer dismissed by button: %r", removed.get("label"))
    return removed


def snooze_timer(timer_id: str, seconds: int = TIMER_SNOOZE_SECONDS) -> bool:
    """Restart a timer to end ``seconds`` from now. False if it doesn't exist."""

    def snooze(timers):
        timer = timers.get(timer_id)
        if not _valid(timer):
            return False
        timer["ends_at"] = int(time.time()) + seconds
        timer["fired"] = False
        return True

    return _mutate(snooze)


def timer_overlay(settings: dict | None = None) -> dict | None:
    """The full-screen alert for the oldest done timer, or None if none are done."""
    done = [t for t in list_timers(settings) if t["done"]]
    if not done:
        return None
    oldest = done[0]
    return {
        "kind": "timer",
        "label": oldest["label"],
        "ended_at": oldest["ends_at"],
        "count": len(done),
    }


def _mark_fired() -> list[str]:
    """Flag timers that just ended as fired. Returns their labels."""
    now = time.time()

    def due(t) -> bool:
        return _valid(t) and t["ends_at"] <= now and not t.get("fired")

    # Only take the write path when a timer actually needs marking, so the
    # 1-second tick is a plain read almost all of the time.
    raw = read_settings().get("timers")
    if not isinstance(raw, dict) or not any(due(t) for t in raw.values()):
        return []

    def mark(timers):
        labels = []
        for t in timers.values():
            if due(t):
                t["fired"] = True
                labels.append(str(t.get("label") or TIMER_DEFAULT_LABEL))
        return labels

    return _mutate(mark)


def _tick() -> None:
    labels = _mark_fired()
    if not labels:
        return
    logger.info("Timer done: %s", ", ".join(repr(l) for l in labels))
    # The alert is an overlay drawn by the running display, so the display has
    # to be on to show it. Turn it on once, when the timer first ends.
    if not is_running():
        mode = read_settings().get("active_display", "clock")
        start_display(mode)
        logger.info("Timer: display was off, started %s to show the alert", mode)


async def run_timer_watcher() -> None:
    """Background loop: notice timers ending and wake the display for them."""
    logger.info("Timer watcher started (tick %ss)", TICK_SECONDS)
    while True:
        try:
            # WiFi-setup mode owns the panel (mirrors the scheduler's guard).
            if WIFI_FLAG.exists():
                await asyncio.to_thread(_tick)
        except Exception:
            logger.exception("Timer watcher tick crashed (continuing)")
        await asyncio.sleep(TICK_SECONDS)
