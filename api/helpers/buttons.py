import asyncio
import logging
import time

from constants import DISPLAY_MODES, BUTTON_1_PIN, BUTTON_2_PIN
from helpers.config import read_settings, write_settings
from helpers.process import start_display

logger = logging.getLogger(__name__)

FACTORY_RESET_HOLD_SECONDS = 10


class ButtonManager:
    def __init__(self):
        self._gpio = None
        self._both_held_since: float | None = None

    def _init_gpio(self):
        global _gpio_instance
        try:
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(BUTTON_1_PIN, GPIO.IN)
            GPIO.setup(BUTTON_2_PIN, GPIO.IN)
            self._gpio = GPIO
            logger.info(
                f"GPIO buttons initialized (pins {BUTTON_1_PIN}, {BUTTON_2_PIN})"
            )
        except Exception as e:
            logger.warning(f"GPIO buttons not available: {e}")

    def _switch(self, mode: str) -> None:
        start_display(mode)
        settings = read_settings()
        settings["active_display"] = mode
        write_settings(settings)
        logger.info(f"Button switched display to {mode}")

    def _factory_reset(self) -> None:
        # TODO: replace log with actual factory reset call once verified
        # from helpers.process import stop_display
        # from helpers.config import reset_settings
        # from helpers.wifi_state import WIFI_FLAG
        # import subprocess, pathlib
        # stop_display(); reset_settings(); ...touch marker...; subprocess.run(["sudo", "reboot"])
        logger.info("Factory reset triggered — hold detected for 10 seconds")

    async def _wait_for_release(self, GPIO) -> None:
        while (
            GPIO.input(BUTTON_1_PIN) == GPIO.LOW or GPIO.input(BUTTON_2_PIN) == GPIO.LOW
        ):
            await asyncio.sleep(0.05)

    async def poll(self) -> None:
        self._init_gpio()
        if self._gpio is None:
            return

        GPIO = self._gpio
        btn1_last = GPIO.HIGH
        btn2_last = GPIO.HIGH

        while True:
            try:
                btn1 = GPIO.input(BUTTON_1_PIN)
                btn2 = GPIO.input(BUTTON_2_PIN)
                both_held = btn1 == GPIO.LOW and btn2 == GPIO.LOW

                if both_held:
                    if self._both_held_since is None:
                        logger.info(
                            "Both buttons held — starting factory reset countdown"
                        )
                        self._both_held_since = time.monotonic()
                    elif (
                        time.monotonic() - self._both_held_since
                        >= FACTORY_RESET_HOLD_SECONDS
                    ):
                        self._both_held_since = None
                        self._factory_reset()
                        await self._wait_for_release(GPIO)
                        btn1_last = GPIO.HIGH
                        btn2_last = GPIO.HIGH
                        continue
                else:
                    self._both_held_since = None

                    if btn1 == GPIO.LOW and btn1_last == GPIO.HIGH:
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

                    if btn2 == GPIO.LOW and btn2_last == GPIO.HIGH:
                        logger.info("Button 2 pressed (cycle right)")
                        current = read_settings().get(
                            "active_display", DISPLAY_MODES[0]
                        )
                        idx = (
                            DISPLAY_MODES.index(current)
                            if current in DISPLAY_MODES
                            else 0
                        )
                        self._switch(DISPLAY_MODES[(idx + 1) % len(DISPLAY_MODES)])

                btn1_last = btn1
                btn2_last = btn2

            except Exception as e:
                logger.error(f"Button poll error: {e}")

            await asyncio.sleep(0.05)


async def poll_buttons() -> None:
    await ButtonManager().poll()
