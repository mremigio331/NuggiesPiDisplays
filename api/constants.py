DISPLAY_MODES = ["clock", "mta", "sports", "stocks", "text", "weather"]

# Sport cycle order for the both-button short-hold (sports mode). Matches the
# display's _SPORT_CONFIG registry and the web UI's alphabetical league order.
SPORTS_CYCLE = [
    "favorites",
    "mlb",
    "nba",
    "wnba",
    "nfl",
    "ncaaf",
    "nhl",
    "nwsl",
    "epl",
    "laliga",
    "bundesliga",
]

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

# Power button wiring (Adafruit Rugged Metal Pushbutton 16mm, 6V RGB, #3350)
#
# Switch (momentary, separate from the LED)
#   Gold tab → physical pin 5  (GPIO 3)
#   Gold tab → physical pin 6  (GND)
#
# RGB LED ring — common anode, built-in resistor, active-LOW cathodes
#   C+ (anode) → physical pin 18  (GPIO 24, drive HIGH to power the LED)
#   R          → physical pin 19  (GPIO 10, LOW = red on)
#   G          → physical pin 21  (GPIO 9,  LOW = green on)
#   B          → physical pin 23  (GPIO 11, LOW = blue on)
#
# GPIO 24 is the matrix HAT's "E" address line, unused by a 32-row panel.
# GPIO 9/10/11 are the SPI pins — free only while SPI stays disabled.

# Read by ButtonManager: tap toggles the display, hold 5s shuts the Pi down.
# While the Pi is off, a press wakes it (firmware, no software) — that's why
# it's on GPIO 3. GPIO 3 is also I2C SCL, so keep I2C disabled. setup.sh removes
# `dtoverlay=gpio-shutdown`, which would claim this pin and make every press a
# shutdown.
POWER_BUTTON_PIN = 3  # GPIO 3, physical pin 5

POWER_LED_ANODE_PIN = 24  # GPIO 24, physical pin 18
POWER_LED_RED_PIN = 10  # GPIO 10, physical pin 19
POWER_LED_GREEN_PIN = 9  # GPIO 9, physical pin 21
POWER_LED_BLUE_PIN = 11  # GPIO 11, physical pin 23
