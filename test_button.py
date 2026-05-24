import RPi.GPIO as GPIO
import time

BUTTON_1 = 25  # GPIO 25, pin 22
BUTTON_2 = 7  # GPIO 7,  pin 26

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_1, GPIO.IN)
GPIO.setup(BUTTON_2, GPIO.IN)

try:
    while True:
        if GPIO.input(BUTTON_1) == GPIO.LOW:
            print("Button 1 pressed!")
        if GPIO.input(BUTTON_2) == GPIO.LOW:
            print("Button 2 pressed!")
        time.sleep(0.1)
except KeyboardInterrupt:
    GPIO.cleanup()
