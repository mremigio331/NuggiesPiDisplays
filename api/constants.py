DISPLAY_MODES = ["clock", "mta", "stocks", "weather"]

# Button wiring (Adafruit STEMMA tactile button, 3-wire: red/black/white)
#
# Button 1 — cycle left
#   White (signal) → physical pin 22  (GPIO 25)
#   Red   (3.3V)   → physical pin 17  (3.3V)
#   Black (GND)    → physical pin 20  (GND)
#
# Button 2 — cycle right
#   White (signal) → physical pin 35  (GPIO 19)
#   Red   (3.3V)   → physical pin 1   (3.3V)
#   Black (GND)    → physical pin 34  (GND)

BUTTON_1_PIN = 25  # GPIO 25, physical pin 22
BUTTON_2_PIN = 19  # GPIO 19, physical pin 35
