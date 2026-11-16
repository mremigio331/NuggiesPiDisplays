"""Power button LED wiring test.

Powers the LED anode, shows red -> green -> blue -> white for 1 second each,
then leaves the LED green.

Run from the project root:  python3 test_power_led.py

If a color comes out wrong, a wire is swapped:
  - Says RED but you see green  -> R and G wires are swapped (pins 19 and 21)
  - Says RED but you see blue   -> R and B wires are swapped (pins 19 and 23)
  - Says GREEN but you see blue -> G and B wires are swapped (pins 21 and 23)
  - One color never lights      -> that cathode wire is loose (R=19, G=21, B=23)
  - Nothing lights at all       -> C+ isn't on pin 18 (GPIO 24), or it's loose
  - WHITE looks pink/odd        -> one cathode is loose; check which step failed
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "api"))
from constants import (
    POWER_LED_ANODE_PIN,
    POWER_LED_BLUE_PIN,
    POWER_LED_GREEN_PIN,
    POWER_LED_RED_PIN,
)

import RPi.GPIO as GPIO

# Common anode: the anode is HIGH, and a cathode LOW turns its color ON.
ON = GPIO.LOW
OFF = GPIO.HIGH

CATHODES = {
    "red": POWER_LED_RED_PIN,  # GPIO 10, physical pin 19
    "green": POWER_LED_GREEN_PIN,  # GPIO 9, physical pin 21
    "blue": POWER_LED_BLUE_PIN,  # GPIO 11, physical pin 23
}

STEPS = [
    ("red", ["red"]),
    ("green", ["green"]),
    ("blue", ["blue"]),
    ("white", ["red", "green", "blue"]),
]


def show(colors: list[str]) -> None:
    for name, pin in CATHODES.items():
        GPIO.output(pin, ON if name in colors else OFF)


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
# Anode HIGH powers the LED (GPIO 24, physical pin 18).
GPIO.setup(POWER_LED_ANODE_PIN, GPIO.OUT, initial=GPIO.HIGH)
# All cathodes start HIGH = off.
for pin in CATHODES.values():
    GPIO.setup(pin, GPIO.OUT, initial=OFF)

print(f"Anode on GPIO {POWER_LED_ANODE_PIN}. Cycling colors...")

for label, colors in STEPS:
    print(f"  {label.upper()}")
    show(colors)
    time.sleep(1)

# No GPIO.cleanup() — that would turn the LED off. Leave it green.
show(["green"])
print("Done. LED left GREEN.")
