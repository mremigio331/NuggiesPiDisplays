import asyncio
import logging
import math
import threading
import time

from constants import (
    POWER_LED_ANODE_PIN,
    POWER_LED_BLUE_PIN,
    POWER_LED_GREEN_PIN,
    POWER_LED_RED_PIN,
)
from helpers.wifi_state import WIFI_FLAG

logger = logging.getLogger(__name__)

# How often the status loop re-checks device state (display on, update, WiFi).
STATUS_POLL_SECONDS = 2
# A mode switch stops the old display before starting the new one. Only call
# the display "off" once it has stayed stopped this long, so a switch doesn't
# flash the LED red.
OFF_SETTLE_SECONDS = 5
# Pulse: one full dim -> bright -> dim breath, drawn with software PWM.
PULSE_PERIOD_SECONDS = 2.0
PULSE_STEP_SECONDS = 0.03
PWM_HZ = 200

# Cathode order used by COLORS below.
_CATHODES = (POWER_LED_RED_PIN, POWER_LED_GREEN_PIN, POWER_LED_BLUE_PIN)

# Brightness of each cathode for each color, in (red, green, blue) order:
# 1 = full, 0 = off. The LED is common-anode: anode HIGH powers it, a cathode
# LOW lights that color. Colors with only 0s and 1s are plain pin writes; a
# color with a level in between is held with software PWM.
COLORS: dict[str, tuple[float, float, float]] = {
    "off": (0, 0, 0),
    "red": (1, 0, 0),
    "green": (0, 1, 0),
    "blue": (0, 0, 1),
    "yellow": (1, 1, 0),
    "cyan": (0, 1, 1),
    "magenta": (1, 0, 1),
    "white": (1, 1, 1),
}


def _needs_pwm(name: str) -> bool:
    return any(0 < level < 1 for level in COLORS[name])


# Status colors:
#   green          display on
#   blue           display on, and an update is ready to install (checked
#                  hourly by helpers/update_check.py)
#   blue, pulsing  update (or factory reset) in progress
#   red            display off (power button tap / schedule), or the Pi is
#                  rebooting or the API service is stopping
#   red, pulsing   shutting down (power button held)
#   white, pulsing booting — scripts/boot_led.py, until the API takes over
#   green, pulsing WiFi setup / captive-portal mode
#   dark           Pi fully halted — nothing drives the LED


class PowerLED:
    def __init__(self):
        self._gpio = None
        self._lock = threading.Lock()  # GPIO calls + latch state
        self._draw_lock = threading.Lock()  # one set_color at a time
        self._color: str | None = None
        self._pulsing = False
        self._pulse_stop: threading.Event | None = None
        self._pulse_thread: threading.Thread | None = None
        # A latched (color, pulse) wins over the status loop until unlatched.
        # Used for one-way states (reboot, shutdown, factory reset) the loop
        # can't detect.
        self._latched: tuple[str, bool] | None = None
        self._off_since: float | None = None
        self._init_warned = False

    @property
    def available(self) -> bool:
        return self._gpio is not None

    def init(self) -> None:
        """Set up the LED pins as outputs: anode HIGH, all cathodes HIGH (off)."""
        with self._lock:
            if self._gpio is not None:
                return
            try:
                import RPi.GPIO as GPIO

                GPIO.setmode(GPIO.BCM)
                # The pins are never released (no GPIO.cleanup — that would also
                # reset the button pins), so an API restart finds them already
                # set up as outputs. That's expected; silence the reuse warning.
                GPIO.setwarnings(False)
                GPIO.setup(POWER_LED_ANODE_PIN, GPIO.OUT, initial=GPIO.HIGH)
                for pin in _CATHODES:
                    GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)
                self._gpio = GPIO
                self._color = "off"
                logger.info(
                    f"Power LED initialized (anode {POWER_LED_ANODE_PIN}, "
                    f"R/G/B {POWER_LED_RED_PIN}/{POWER_LED_GREEN_PIN}/{POWER_LED_BLUE_PIN})"
                )
            except Exception as e:
                # Retried every poll; warn once, not every 2s (a dev machine
                # with no GPIO would otherwise log forever).
                if not self._init_warned:
                    logger.warning(f"Power LED not available (will retry): {e}")
                    self._init_warned = True

    def set_color(self, name: str, pulse: bool = False) -> None:
        """Show *name* solid, or breathing when *pulse* is True."""
        if name not in COLORS:
            raise ValueError(f"Unknown power LED color: {name!r}")
        if self._gpio is None:
            return
        with self._draw_lock:
            if pulse or _needs_pwm(name):
                # PWM thread already drawing exactly this — leave it running.
                if self._pulse_thread is not None and (name, pulse) == (
                    self._color,
                    self._pulsing,
                ):
                    return
                self._stop_pulse()
                self._start_pulse(name, pulse)
            else:
                self._stop_pulse()
                self._write_solid(name)
            if (name, pulse) != (self._color, self._pulsing):
                logger.debug(f"Power LED → {name}{' (pulse)' if pulse else ''}")
            self._color, self._pulsing = name, pulse

    def latch(self, name: str, pulse: bool = False) -> None:
        """Show *name* and hold it, ignoring the status loop, until unlatch()."""
        with self._lock:
            self._latched = (name, pulse)
        self.set_color(name, pulse)

    def unlatch(self) -> None:
        """Release a latched color (e.g. a reboot failed) and show live status."""
        with self._lock:
            self._latched = None
        self.show_status()

    def show_status(self) -> None:
        with self._lock:
            latched = self._latched
        if latched:
            self.set_color(*latched)
            return
        status = self._status_color()
        if status:
            self.set_color(*status)

    def _status_color(self) -> tuple[str, bool] | None:
        """(color, pulse) for the live device state, or None to keep the current one.

        Only single colors (red, green, blue) are used for status: on this LED
        red overpowers green, so mixes like yellow or amber just read as red.
        """
        # Lazy import: helpers.system imports this module.
        from helpers.process import is_running
        from helpers.system import read_update_lock

        if read_update_lock() is not None:
            return ("blue", True)
        if not WIFI_FLAG.exists():
            return ("green", True)
        if is_running():
            self._off_since = None
            return ("blue", False) if _update_available() else ("green", False)
        now = time.monotonic()
        if self._off_since is None:
            self._off_since = now
        if now - self._off_since < OFF_SETTLE_SECONDS:
            return None  # likely mid mode switch
        return ("red", False)

    # --- GPIO drawing ---

    def _write_solid(self, name: str) -> None:
        # Written every time, not only on change: the boot pulser (a separate
        # process) may still have been driving these pins when the API started,
        # so each status poll re-asserts the real state.
        GPIO = self._gpio
        with self._lock:
            try:
                GPIO.output(POWER_LED_ANODE_PIN, GPIO.HIGH)
                for pin, on in zip(_CATHODES, COLORS[name]):
                    GPIO.output(pin, GPIO.LOW if on else GPIO.HIGH)
            except Exception as e:
                logger.warning(f"Power LED set_color({name!r}) failed: {e}")

    def _start_pulse(self, name: str, pulse: bool = True) -> None:
        stop = threading.Event()
        self._pulse_stop = stop
        self._pulse_thread = threading.Thread(
            target=self._pulse_loop, args=(name, stop, pulse), daemon=True
        )
        self._pulse_thread.start()

    def _stop_pulse(self) -> None:
        if self._pulse_stop is None:
            return
        self._pulse_stop.set()
        if self._pulse_thread is not threading.current_thread():
            self._pulse_thread.join(timeout=1)
        self._pulse_stop = None
        self._pulse_thread = None

    def _pulse_loop(self, name: str, stop: threading.Event, pulse: bool = True) -> None:
        """Draw *name* with software PWM: breathing when *pulse*, else held steady
        (for mixed colors that need a cathode part-way on)."""
        GPIO = self._gpio
        lit = [(pin, level) for pin, level in zip(_CATHODES, COLORS[name]) if level > 0]
        pwms = []
        try:
            with self._lock:
                GPIO.output(POWER_LED_ANODE_PIN, GPIO.HIGH)
                for pin in _CATHODES:
                    GPIO.output(pin, GPIO.HIGH)
                # Duty cycle is the share of time HIGH, and HIGH is OFF for a
                # cathode, so 100 = dark and 0 = full brightness.
                for pin, level in lit:
                    pwm = GPIO.PWM(pin, PWM_HZ)
                    pwm.start(100 if pulse else 100 - 100 * level)
                    pwms.append((pwm, level))
            if not pulse:
                stop.wait()  # steady: hold the duty cycles until stopped
                return
            start = time.monotonic()
            while not stop.wait(PULSE_STEP_SECONDS):
                phase = (time.monotonic() - start) / PULSE_PERIOD_SECONDS
                breath = (1 - math.cos(2 * math.pi * phase)) / 2  # 0..1..0
                with self._lock:
                    for pwm, level in pwms:
                        pwm.ChangeDutyCycle(100 - 100 * breath * level)
        except Exception as e:
            logger.warning(f"Power LED pulse ({name!r}) failed: {e}")
        finally:
            with self._lock:
                for pwm, _ in pwms:
                    try:
                        pwm.stop()
                    except Exception:
                        pass


def _update_available() -> bool:
    """True when the hourly check found a newer build for this device's stage."""
    try:
        from helpers.update_check import get_status

        return bool(get_status().update_available)
    except Exception:
        return False


power_led = PowerLED()


async def run_power_led() -> None:
    """Initialize the LED, then keep it showing the device status.

    Init is retried every poll until it works: at boot the API starts while
    scripts/boot_led.py still holds the LED pins ('GPIO busy'), and that script
    only lets go once the API answers.
    """
    while True:
        try:
            if not power_led.available:
                power_led.init()
            if power_led.available:
                power_led.show_status()
        except Exception:
            logger.exception("Power LED status update failed")
        await asyncio.sleep(STATUS_POLL_SECONDS)
