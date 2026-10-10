import asyncio
import logging
import threading
import time

from constants import DISPLAY_MODES, SPORTS_CYCLE, BUTTON_1_PIN, BUTTON_2_PIN
from helpers.config import read_settings, write_settings, write_overlay
from helpers.process import start_display
from helpers.system import SystemManager
from helpers.wifi_state import WIFI_FLAG

logger = logging.getLogger(__name__)

RESTART_HOLD_SECONDS = 10
FACTORY_RESET_HOLD_SECONDS = 10
# Both-button hold bands:
#   < CYCLE_MIN            -> ignored (accidental tap)
#   CYCLE_MIN .. RESET     -> on release, cycle the inner item (sports: sport)
#   PROMPT .. RESET        -> show "Hold Ns for Factory Reset" countdown overlay
#   >= RESET               -> factory reset
BOTH_CYCLE_MIN_SECONDS = 3
BOTH_PROMPT_SECONDS = 5


class ButtonManager:
    def __init__(self):
        self._gpio = None
        # Both-buttons hold (factory reset)
        self._hold_start: float | None = None
        self._hold_lock = threading.Lock()
        # Button 1 solo hold (restart)
        self._btn1_monitoring = False
        self._btn1_lock = threading.Lock()

    def _init_gpio(self):
        try:
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(BUTTON_1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(BUTTON_2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                BUTTON_1_PIN, GPIO.FALLING, callback=self._on_btn1, bouncetime=200
            )
            GPIO.add_event_detect(
                BUTTON_2_PIN, GPIO.FALLING, callback=self._on_btn2, bouncetime=200
            )
            self._gpio = GPIO
            logger.info(
                f"GPIO buttons initialized (pins {BUTTON_1_PIN}, {BUTTON_2_PIN})"
            )
        except Exception as e:
            logger.warning(f"GPIO buttons not available: {e}")

    # --- GPIO interrupt callbacks (run in GPIO's internal thread) ---

    def _on_btn1(self, channel):
        if self._gpio.input(BUTTON_2_PIN) == self._gpio.LOW:
            self._start_both_hold()
            return
        with self._btn1_lock:
            if self._btn1_monitoring:
                return
            self._btn1_monitoring = True
        threading.Thread(target=self._monitor_btn1_hold, daemon=True).start()

    def _on_btn2(self, channel):
        if self._gpio.input(BUTTON_1_PIN) == self._gpio.LOW:
            self._start_both_hold()
            return
        # A both-buttons hold is already counting down — a re-fired btn2 edge from
        # contact chatter must not be treated as a solo cycle (which would switch
        # the display mid-hold and confuse the user).
        with self._hold_lock:
            if self._hold_start is not None:
                return
        if WIFI_FLAG.exists():
            logger.info("Button 2 pressed (cycle right)")
            current = read_settings().get("active_display", DISPLAY_MODES[0])
            idx = DISPLAY_MODES.index(current) if current in DISPLAY_MODES else 0
            self._switch(DISPLAY_MODES[(idx + 1) % len(DISPLAY_MODES)])
        else:
            logger.info("Button 2 pressed — ignored (WiFi setup mode)")

    # --- Button 1 solo hold monitor (restart or cycle left) ---

    def _monitor_btn1_hold(self):
        GPIO = self._gpio
        press_time = time.monotonic()
        logged_countdown = False
        try:
            while True:
                time.sleep(0.05)

                # Button 2 also pressed, or a both-buttons hold is already armed —
                # hand off to the factory-reset monitor and skip the solo cycle.
                if GPIO.input(BUTTON_2_PIN) == GPIO.LOW:
                    return
                with self._hold_lock:
                    if self._hold_start is not None:
                        return

                elapsed = time.monotonic() - press_time

                # Button released before threshold — cycle left.
                if GPIO.input(BUTTON_1_PIN) != GPIO.LOW:
                    if elapsed < RESTART_HOLD_SECONDS:
                        if WIFI_FLAG.exists():
                            logger.info("Button 1 pressed (cycle left)")
                            current = read_settings().get(
                                "active_display", DISPLAY_MODES[0]
                            )
                            idx = (
                                DISPLAY_MODES.index(current)
                                if current in DISPLAY_MODES
                                else 0
                            )
                            self._switch(DISPLAY_MODES[(idx - 1) % len(DISPLAY_MODES)])
                        else:
                            logger.info("Button 1 pressed — ignored (WiFi setup mode)")
                    return

                if not logged_countdown and elapsed >= 1:
                    logger.info("Button 1 held — starting restart countdown")
                    logged_countdown = True

                if elapsed >= RESTART_HOLD_SECONDS:
                    self._restart()
                    while GPIO.input(BUTTON_1_PIN) == GPIO.LOW:
                        time.sleep(0.05)
                    return
        finally:
            with self._btn1_lock:
                self._btn1_monitoring = False

    # --- Both-buttons hold monitor (factory reset) ---

    def _start_both_hold(self):
        with self._hold_lock:
            if self._hold_start is not None:
                return
            self._hold_start = time.monotonic()
            logger.info("Both buttons held — starting both-hold monitor")
        threading.Thread(target=self._monitor_both_hold, daemon=True).start()

    def _monitor_both_hold(self):
        """State machine for a both-buttons hold.

        Actions happen WHILE held (not on release) so the user gets immediate
        feedback that a threshold was crossed:
          at BOTH_CYCLE_MIN_SECONDS  cycle the inner item once (sports mode:
                                     next sport). Fires at the 3s mark so the
                                     display changes under your fingers — no need
                                     to let go. Other modes do nothing.
          >= BOTH_PROMPT_SECONDS     show the "Hold Ns for Factory Reset" overlay
                                     countdown while still held
          >= FACTORY_RESET_HOLD      blank the display ("Factory Reset") and fire
                                     the reset
        Released before BOTH_CYCLE_MIN_SECONDS does nothing (accidental tap).

        Mechanical buttons chatter, so a single sampled HIGH is not treated as a
        release — both must read released continuously for RELEASE_DEBOUNCE
        before the hold is considered broken.
        """
        GPIO = self._gpio
        RELEASE_DEBOUNCE_SECONDS = 0.3
        released_since: float | None = None
        last_progress_log = 0.0
        prompt_shown_for = -1  # last whole-second value pushed to the overlay
        cycled = False  # inner cycle already fired at the 3s mark
        try:
            while True:
                time.sleep(0.05)

                b1 = GPIO.input(BUTTON_1_PIN) == GPIO.LOW
                b2 = GPIO.input(BUTTON_2_PIN) == GPIO.LOW
                both_down = b1 and b2

                if both_down:
                    released_since = None
                else:
                    now = time.monotonic()
                    if released_since is None:
                        released_since = now
                    elif now - released_since >= RELEASE_DEBOUNCE_SECONDS:
                        with self._hold_lock:
                            held = (
                                time.monotonic() - self._hold_start
                                if self._hold_start
                                else 0.0
                            )
                            self._hold_start = None
                        # Any countdown overlay we put up must be cleared on
                        # release so the display resumes normal rendering.
                        if prompt_shown_for >= 0:
                            self._set_overlay(None)
                        logger.info(
                            f"Both-hold released after {held:.1f}s "
                            f"(cycled={cycled})"
                        )
                        return
                    continue

                with self._hold_lock:
                    if self._hold_start is None:
                        return
                    elapsed = time.monotonic() - self._hold_start

                if elapsed - last_progress_log >= 1.0:
                    logger.info(
                        f"Both-hold: {elapsed:.0f}s / {FACTORY_RESET_HOLD_SECONDS}s"
                    )
                    last_progress_log = elapsed

                # At the 3s mark, cycle the inner item once WHILE still held, so
                # the change happens under the user's fingers (immediate feedback
                # that 3s elapsed). Sports mode only; other modes reserved.
                if not cycled and elapsed >= BOTH_CYCLE_MIN_SECONDS:
                    cycled = True
                    active = read_settings().get("active_display", DISPLAY_MODES[0])
                    if active == "sports":
                        self._cycle_sport()
                    else:
                        logger.info(
                            f"Both-hold hit {BOTH_CYCLE_MIN_SECONDS}s in {active!r} "
                            "— no inner cycle defined for this mode"
                        )

                # From PROMPT_SECONDS on, show a live countdown overlay so the
                # user sees how long is left before the reset fires.
                if elapsed >= BOTH_PROMPT_SECONDS:
                    seconds_left = max(
                        0, int(round(FACTORY_RESET_HOLD_SECONDS - elapsed))
                    )
                    if seconds_left != prompt_shown_for:
                        prompt_shown_for = seconds_left
                        self._set_overlay(
                            {"kind": "reset_prompt", "seconds_left": seconds_left}
                        )

                if elapsed >= FACTORY_RESET_HOLD_SECONDS:
                    logger.info("Both-hold reached factory-reset threshold — firing")
                    with self._hold_lock:
                        self._hold_start = None
                    # Blank the display with the running banner, then reset.
                    self._set_overlay({"kind": "reset_running"})
                    self._factory_reset()
                    while (
                        GPIO.input(BUTTON_1_PIN) == GPIO.LOW
                        or GPIO.input(BUTTON_2_PIN) == GPIO.LOW
                    ):
                        time.sleep(0.05)
                    return
        except Exception:
            logger.exception("Both-hold monitor crashed")
            with self._hold_lock:
                self._hold_start = None
            self._set_overlay(None)

    def _cycle_sport(self) -> None:
        """Advance sports mode to the next sport in SPORTS_CYCLE."""
        settings = read_settings()
        sports = settings.setdefault("sports", {})
        current = sports.get("sport", SPORTS_CYCLE[0])
        idx = SPORTS_CYCLE.index(current) if current in SPORTS_CYCLE else 0
        nxt = SPORTS_CYCLE[(idx + 1) % len(SPORTS_CYCLE)]
        sports["sport"] = nxt
        # A pending one-shot jump belongs to the old league; clear it on switch.
        if nxt != current:
            sports["force_event_id"] = ""
        write_settings(settings)
        logger.info(f"Both-hold cycled sport: {current!r} → {nxt!r}")

    def _set_overlay(self, overlay: dict | None) -> None:
        try:
            write_overlay(overlay)
        except Exception as e:
            logger.error(f"Failed to set display overlay: {e}")

    # --- Actions ---

    def _switch(self, mode: str) -> None:
        start_display(mode)
        settings = read_settings()
        settings["active_display"] = mode
        write_settings(settings)
        logger.info(f"Button switched display to {mode}")

    def _restart(self) -> None:
        logger.info("Restart triggered — button 1 held for 10 seconds")
        try:
            SystemManager().reboot()
        except Exception as e:
            logger.error(f"Restart failed: {e}")

    def _factory_reset(self) -> None:
        logger.info("Factory reset triggered — both buttons held for 10 seconds")
        try:
            SystemManager().factory_reset_wifi()
        except Exception as e:
            logger.error(f"Factory reset failed: {e}")

    async def poll(self) -> None:
        self._init_gpio()
        if self._gpio is None:
            return
        while True:
            await asyncio.sleep(3600)


async def poll_buttons() -> None:
    await ButtonManager().poll()
