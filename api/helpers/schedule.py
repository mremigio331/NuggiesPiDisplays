"""Time-of-day display scheduler.

Runs as a background task in the API lifespan. It is EDGE-triggered: a rule
fires only at the moment its ``time`` (device-local ``HH:MM``) arrives, and
then switches the LED display to that rule's mode (and sub-option, e.g. sports
league).

What this deliberately does NOT do:

* It does not snap the display when you merely ENABLE the schedule. Turning the
  schedule on changes nothing until the next rule time actually arrives — so
  enabling at 18:14 with an 18:05 rule waits for the following rule, it does not
  jump back to the 18:05 mode.
* It does not fight manual switches. Switch the mode by hand (web UI, button)
  and it stays until the next rule time comes around; the schedule simply
  re-asserts at that next edge. There is no auto-off.

Firing is de-duplicated per minute: the tick runs every ``TICK_SECONDS`` so a
given ``HH:MM`` is seen on more than one tick, but a rule fires at most once per
calendar minute (tracked by ``_last_fired_stamp``).
"""

import asyncio
import logging
from datetime import datetime

from helpers.config import (
    read_schedule,
    read_settings,
    write_settings,
    write_display_brightness,
)
from helpers.process import start_display, stop_display, is_running
from helpers.wifi_state import WIFI_FLAG

logger = logging.getLogger(__name__)

# How often the loop wakes. 30s guarantees we observe every HH:MM minute at
# least once (a minute spans ~2 ticks) without busy-spinning.
TICK_SECONDS = 30

# Stamp ("YYYY-MM-DD HH:MM|mode") of the rule edge we last fired, so a rule
# fires once when its minute arrives and not again on the second tick inside
# that same minute. None until the first fire this run.
_last_fired_stamp: str | None = None


def _apply_option(mode: str, option: str | None) -> None:
    """Pin a mode's sub-option (e.g. sports league) before the display starts.

    The display reads its sub-setting from settings at launch, so writing it
    here and then calling start_display(mode) brings the display up on the
    chosen sub-option. Only sports has one today:
    option -> settings["sports"]["sport"].
    """
    if not option:
        return
    if mode == "sports":
        settings = read_settings()
        sports = settings.setdefault("sports", {})
        if sports.get("sport") != option:
            # A pending one-shot jump belongs to the old league; clear on switch
            # (mirrors the sports /settings update path).
            sports["force_event_id"] = ""
        sports["sport"] = option
        write_settings(settings)
        logger.info("Schedule: pinned sports league %r", option)


def _fire(rule: dict) -> None:
    """Carry out a schedule rule at its time, via the same paths manual controls use.

    Actions:
      mode       -> switch to a display mode (+ optional sub-option, e.g. league)
      power      -> turn the display off (stop) or on (start active mode)
      brightness -> set LED brightness, then restart the running mode so it takes
                    effect immediately (brightness is read at display start)
    """
    action = rule.get("action", "mode")
    t = rule["time"]

    if action == "power":
        if rule["power"] == "off":
            stop_display()
            logger.info("Schedule: fired %s rule -> power OFF", t)
        else:
            mode = read_settings().get("active_display", "clock")
            start_display(mode)
            logger.info("Schedule: fired %s rule -> power ON (%s)", t, mode)
        return

    if action == "brightness":
        value = write_display_brightness(rule["brightness"])
        # Brightness is applied by the matrix at display start, so restart the
        # currently-running mode to make the new level visible now. If nothing
        # is running (display powered off), just persist it for the next start.
        if is_running():
            mode = read_settings().get("active_display", "clock")
            start_display(mode)
        logger.info("Schedule: fired %s rule -> brightness %s", t, value)
        return

    # Default: mode switch.
    mode = rule["mode"]
    option = rule.get("option")
    _apply_option(mode, option)
    start_display(mode)
    settings = read_settings()
    settings["active_display"] = mode
    write_settings(settings)
    logger.info(
        "Schedule: fired %s rule -> %r%s",
        t,
        mode,
        f" ({option})" if option else "",
    )


async def _tick() -> None:
    global _last_fired_stamp

    schedule = read_schedule()
    if not schedule["enabled"]:
        return
    rules = schedule["rules"]
    if not rules:
        return

    now = datetime.now()
    hhmm = now.strftime("%H:%M")

    # Find a rule whose time is exactly the current minute. rules is normalized
    # (deduped by time), so at most one matches.
    rule = next((r for r in rules if r["time"] == hhmm), None)
    if rule is None:
        return

    stamp = f"{now.strftime('%Y-%m-%d %H:%M')}|{rule['time']}"
    if stamp == _last_fired_stamp:
        # Already fired this exact edge on an earlier tick this minute.
        return

    try:
        _fire(rule)
        _last_fired_stamp = stamp
    except Exception as e:
        logger.warning("Schedule: failed to fire %s rule: %s", rule["time"], e)


async def run_scheduler() -> None:
    """Background loop: fire the day's schedule rules at their times."""
    logger.info("Display scheduler started (edge-triggered, tick %ss)", TICK_SECONDS)
    while True:
        try:
            # Don't drive the matrix while the device is in WiFi-setup mode —
            # the setup display owns the panel then (mirrors main.py's guard).
            if WIFI_FLAG.exists():
                await _tick()
        except Exception:
            logger.exception("Display scheduler tick crashed (continuing)")
        await asyncio.sleep(TICK_SECONDS)
