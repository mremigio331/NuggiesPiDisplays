"""Power button LED: pulse white while the Pi boots, until the API takes over.

Run early in boot by nuggies-led-boot.service (installed by setup.sh). Before
this starts, the firmware already shows solid white from the `gpio=` lines
setup.sh puts in config.txt. This breathes the LED until the API answers on
localhost, then exits and leaves the LED to api/helpers/power_led.py, which
re-asserts its color on every status poll.

Never calls GPIO.cleanup() — that would turn the pins into inputs and drop the
LED dark between this script exiting and the API's next poll.
"""

import math
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
from constants import (
    POWER_LED_ANODE_PIN,
    POWER_LED_BLUE_PIN,
    POWER_LED_GREEN_PIN,
    POWER_LED_RED_PIN,
)

import RPi.GPIO as GPIO

API_URL = "http://localhost:8000/api/system/status"
# Give up after this long so a broken API can't leave the LED breathing forever;
# solid red then means "display off".
TIMEOUT_SECONDS = 300
API_CHECK_SECONDS = 1.0
PULSE_PERIOD_SECONDS = 2.0
PULSE_STEP_SECONDS = 0.03
PWM_HZ = 200

CATHODES = (POWER_LED_RED_PIN, POWER_LED_GREEN_PIN, POWER_LED_BLUE_PIN)


def api_up() -> bool:
    try:
        urllib.request.urlopen(API_URL, timeout=1)
        return True
    except Exception:
        return False


def main() -> None:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(POWER_LED_ANODE_PIN, GPIO.OUT, initial=GPIO.HIGH)
    for pin in CATHODES:
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

    # Common anode: a cathode HIGH is OFF, so duty 100 = dark, 0 = full white.
    pwms = [GPIO.PWM(pin, PWM_HZ) for pin in CATHODES]
    for pwm in pwms:
        pwm.start(0)

    start = time.monotonic()
    next_check = start
    timed_out = False
    try:
        while True:
            now = time.monotonic()
            if now >= next_check:
                if api_up():
                    break
                if now - start >= TIMEOUT_SECONDS:
                    timed_out = True
                    break
                next_check = now + API_CHECK_SECONDS
            phase = (now - start) / PULSE_PERIOD_SECONDS
            level = (1 - math.cos(2 * math.pi * phase)) / 2
            for pwm in pwms:
                pwm.ChangeDutyCycle(100 - 100 * level)
            time.sleep(PULSE_STEP_SECONDS)
    finally:
        for pwm in pwms:
            pwm.stop()
        # Solid white hands over to the API (which repaints within a poll), or
        # red if the API never came up.
        GPIO.output(POWER_LED_RED_PIN, GPIO.LOW)
        GPIO.output(POWER_LED_GREEN_PIN, GPIO.HIGH if timed_out else GPIO.LOW)
        GPIO.output(POWER_LED_BLUE_PIN, GPIO.HIGH if timed_out else GPIO.LOW)


if __name__ == "__main__":
    main()
