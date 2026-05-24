import asyncio
import logging
import threading
import time

from constants import DISPLAY_MODES, BUTTON_1_PIN, BUTTON_2_PIN
from helpers.config import read_settings, write_settings
from helpers.process import start_display
from helpers.system import SystemManager
from helpers.wifi_state import WIFI_FLAG

logger = logging.getLogger(__name__)

RESTART_HOLD_SECONDS = 10
FACTORY_RESET_HOLD_SECONDS = 10


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
        elif WIFI_FLAG.exists():
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

                # Button 2 also pressed — hand off to factory reset, skip cycle.
                if GPIO.input(BUTTON_2_PIN) == GPIO.LOW:
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
            logger.info("Both buttons held — starting factory reset countdown")
        threading.Thread(target=self._monitor_both_hold, daemon=True).start()

    def _monitor_both_hold(self):
        GPIO = self._gpio
        while True:
            time.sleep(0.1)
            if (
                GPIO.input(BUTTON_1_PIN) != GPIO.LOW
                or GPIO.input(BUTTON_2_PIN) != GPIO.LOW
            ):
                with self._hold_lock:
                    self._hold_start = None
                return
            with self._hold_lock:
                if self._hold_start is None:
                    return
                elapsed = time.monotonic() - self._hold_start
            if elapsed >= FACTORY_RESET_HOLD_SECONDS:
                with self._hold_lock:
                    self._hold_start = None
                self._factory_reset()
                return

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
