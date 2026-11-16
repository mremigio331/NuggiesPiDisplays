# Button → GPIO Wiring Map

This maps the physical buttons — two tactile buttons and the RGB power
button — to the Raspberry Pi GPIO header.

> **Wire colors:** Each tactile button uses a **3-wire** cable — **red**, **black**,
> and **white** (Adafruit STEMMA tactile button).
> - 🔴 **Red** = 3.3V power
> - ⚫ **Black** = ground (GND)
> - ⚪ **White** = signal → goes to the button's **GPIO pin**

## Pin assignments

| Button               | ⚪ White (signal)              | 🔴 Red (3.3V)         | ⚫ Black (GND)         |
| -------------------- | ----------------------------- | --------------------- | --------------------- |
| **Button 1** (left)  | **GPIO 25** → physical pin 22 | 3.3V → physical pin 17 | GND → physical pin 20 |
| **Button 2** (right) | **GPIO 19** → physical pin 35 | 3.3V → physical pin 1  | GND → physical pin 34 |

Pin numbers come straight from `api/constants.py`
(`BUTTON_1_PIN = 25`, `BUTTON_2_PIN = 19`).

## Where the pins are on the 40-pin header

The Pi header is two rows. Odd pins are the left column, even pins the right
column, when the board is oriented with the GPIO header along the top edge and
pin 1 at the top-left.

```
       Button 2 RED → 🔴 3.3V  [ 1] [ 2]  5V
                      GPIO  2  [ 3] [ 4]  5V
     Power SWITCH → 🟡 GPIO  3  [ 5] [ 6] 🟡 GND  ← Power SWITCH (other tab)
                      GPIO  4  [ 7] [ 8]  GPIO 14
                         GND  [ 9] [10]  GPIO 15
                     GPIO 17  [11] [12]  GPIO 18
                     GPIO 27  [13] [14]  GND
                     GPIO 22  [15] [16]  GPIO 23
       Button 1 RED → 🔴 3.3V  [17] [18] 💡 GPIO 24  ← Power LED C+ (anode)
     Power LED R → 💡 GPIO 10  [19] [20] ⚫ GND  ← Button 1 BLACK
     Power LED G → 💡 GPIO  9  [21] [22] ⚪ GPIO 25  ← Button 1 WHITE (signal)
     Power LED B → 💡 GPIO 11  [23] [24]  GPIO  8
                         GND  [25] [26]  GPIO  7
                      GPIO  0  [27] [28]  GPIO  1
                      GPIO  5  [29] [30]  GND
                      GPIO  6  [31] [32]  GPIO 12
                     GPIO 13  [33] [34] ⚫ GND  ← Button 2 BLACK
          Button 2 WHITE → ⚪ GPIO 19  [35] [36]  GPIO 16
                     GPIO 26  [37] [38]  GPIO 20
                         GND  [39] [40]  GPIO 21
```

> **Note on red (3.3V):** pin 1 and pin 17 are **both 3.3V**, so Button 1's red
> goes to pin 17 and Button 2's red goes to pin 1 (as wired in
> `api/constants.py`). Either 3.3V pin would power either button — they share
> the same rail.

### Button 1 (cycle left)
- ⚪ **White** → pin **22** (GPIO 25, signal)
- 🔴 **Red** → pin **17** (3.3V)
- ⚫ **Black** → pin **20** (GND)

### Button 2 (cycle right)
- ⚪ **White** → pin **35** (GPIO 19, signal)
- 🔴 **Red** → pin **1** (3.3V)
- ⚫ **Black** → pin **34** (GND)

While a timer alert ("TIME'S UP") is on the board, a tap on Button 1 or
Button 2 dismisses that timer instead of cycling. Holds work as usual.

## Power button

**Adafruit Rugged Metal Pushbutton, 16mm, 6V RGB Momentary (product 3350).**
It has a momentary switch (two gold tabs) that is electrically separate from an
RGB LED ring. The LED has a **common anode** (`C+`) and three cathodes
(`R`, `G`, `B`); the current-limiting resistor is built in.

| Power button tab        | Pi physical pin | BCM GPIO | Role |
| ----------------------- | --------------- | -------- | ---- |
| Gold tab (switch)       | Pin 5           | GPIO 3   | Power switch input (pull-up, press = LOW) |
| Other gold tab (switch) | Pin 6           | GND      | Switch ground |
| `C+` (LED anode)        | Pin 18          | GPIO 24  | Output, driven **HIGH** to power the LED |
| `R` (red cathode)       | Pin 19          | GPIO 10  | Output, LOW = red on |
| `G` (green cathode)     | Pin 21          | GPIO 9   | Output, LOW = green on |
| `B` (blue cathode)      | Pin 23          | GPIO 11  | Output, LOW = blue on |

Pin numbers come from `api/constants.py` (`POWER_BUTTON_PIN = 3`,
`POWER_LED_ANODE_PIN = 24`, `POWER_LED_RED_PIN = 10`,
`POWER_LED_GREEN_PIN = 9`, `POWER_LED_BLUE_PIN = 11`).

### Switch: tap, hold, wake

| Press | Pi state | Result |
| ----- | -------- | ------ |
| Tap | Running | Display on/off (the Pi and website stay up) |
| Hold 5s | Running | Clean Pi shutdown |
| Tap | Off (halted) | Pi boots |

The API reads GPIO 3 (`api/helpers/buttons.py`). Waking a halted Pi is built
into the Pi firmware — shorting GPIO 3 to GND does it with no software running,
which is why the switch is on **GPIO 3 on purpose**.

GPIO 3 is also I2C SCL, so keep I2C disabled. Don't add
`dtoverlay=gpio-shutdown`: it claims GPIO 3 and turns every press into a
shutdown. `setup.sh` removes it if present (takes effect after a reboot).

### LED: active-LOW

The LED is common-anode, so its logic is inverted:

- The anode (GPIO 24) is held **HIGH** to power the LED.
- Pulling a color's cathode **LOW** turns that color **ON**.
- Setting a cathode **HIGH** turns it **OFF**.

Mixing cathodes gives yellow (R+G), cyan (G+B), magenta (R+B) and white (all
three), but red overpowers green on this LED, so status uses only single
colors. `api/helpers/power_led.py` drives it and shows the device status:

| Color          | Meaning |
| -------------- | ------- |
| Green          | Display on |
| Blue           | Display on, and an update is ready (checked hourly) |
| Blue, pulsing  | Update or factory reset in progress |
| Red            | Display off (Pi still on), or rebooting |
| Red, pulsing   | Shutting down (power button held 5s) |
| White, pulsing | Booting |
| Green, pulsing | WiFi setup / captive-portal mode |
| Dark           | Pi fully off |

Booting has two steps. `gpio=24=op,dh` and `gpio=9-11=op,dl` in the boot config
make the firmware show solid white at power-on, before Linux runs. Then
`nuggies-led-boot.service` (`scripts/boot_led.py`) pulses it white until the API
is up and takes over. `setup.sh` adds both.

GPIO 24 is the matrix HAT's "E" address line, which a 32-row panel doesn't use.
GPIO 9/10/11 are the SPI pins — they're free only because SPI is disabled, so
**don't enable SPI**.

## Quick reference — the pins you touch

```
pin  1 🔴 ── Button 2 red   (3.3V)
pin  5 🟡 ── Power switch   (GPIO 3, tap/hold/wake)
pin  6 🟡 ── Power switch   (GND)
pin 17 🔴 ── Button 1 red   (3.3V)
pin 18 💡 ── Power LED C+   (GPIO 24, HIGH)
pin 19 💡 ── Power LED R    (GPIO 10, LOW = on)
pin 20 ⚫ ── Button 1 black (GND)
pin 21 💡 ── Power LED G    (GPIO 9,  LOW = on)
pin 22 ⚪ ── Button 1 white (GPIO 25, signal)
pin 23 💡 ── Power LED B    (GPIO 11, LOW = on)
pin 34 ⚫ ── Button 2 black (GND)
pin 35 ⚪ ── Button 2 white (GPIO 19, signal)
```

## Notes

- The signal pins (GPIO 25 and GPIO 19) are configured as inputs with an
  internal pull-up (`pull_up_down=GPIO.PUD_UP`), so a press reads LOW.
- Any 3.3V pin (1 or 17) and any free GND pin (9, 14, 20, 25, 30, 34, 39) will
  work for the tactile buttons — ground is ground and 3.3V is 3.3V. Pin 6 is
  taken by the power switch. The pins above keep each button's wires grouped
  tidily on the header.
- Test the wiring with `python3 test_button.py` from the project root — it
  prints `Button 1 pressed!` / `Button 2 pressed!` on each press.
- Test the power LED with `python3 test_power_led.py` — it cycles
  red → green → blue → white, then leaves it green.
