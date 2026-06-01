import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "api"))
from constants import BUTTON_1_PIN, BUTTON_2_PIN

import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(BUTTON_2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print(f"Watching buttons on GPIO {BUTTON_1_PIN} and {BUTTON_2_PIN}. Ctrl+C to quit.")

try:
    while True:
        if GPIO.input(BUTTON_1_PIN) == GPIO.LOW:
            print("Button 1 pressed!")
        if GPIO.input(BUTTON_2_PIN) == GPIO.LOW:
            print("Button 2 pressed!")
        time.sleep(0.1)
except KeyboardInterrupt:
    GPIO.cleanup()
