# Button → GPIO Wiring Map

This maps the two physical buttons to the Raspberry Pi GPIO header.

> **Wire colors:** Each button uses a **3-wire** cable — **red**, **black**,
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
                      GPIO  3  [ 5] [ 6]  GND
                      GPIO  4  [ 7] [ 8]  GPIO 14
                         GND  [ 9] [10]  GPIO 15
                     GPIO 17  [11] [12]  GPIO 18
                     GPIO 27  [13] [14]  GND
                     GPIO 22  [15] [16]  GPIO 23
       Button 1 RED → 🔴 3.3V  [17] [18]  GPIO 24
                     GPIO 10  [19] [20] ⚫ GND  ← Button 1 BLACK
                     GPIO  9  [21] [22] ⚪ GPIO 25  ← Button 1 WHITE (signal)
                     GPIO 11  [23] [24]  GPIO  8
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

## Quick reference — the six pins you touch

```
pin  1 🔴 ── Button 2 red   (3.3V)
pin 17 🔴 ── Button 1 red   (3.3V)
pin 20 ⚫ ── Button 1 black (GND)
pin 22 ⚪ ── Button 1 white (GPIO 25, signal)
pin 34 ⚫ ── Button 2 black (GND)
pin 35 ⚪ ── Button 2 white (GPIO 19, signal)
```

## Notes

- The signal pins (GPIO 25 and GPIO 19) are configured as inputs with an
  internal pull-up (`pull_up_down=GPIO.PUD_UP`), so a press reads LOW.
- Any 3.3V pin (1 or 17) and any GND pin (6, 9, 14, 20, 25, 30, 34, 39) will
  work — ground is ground and 3.3V is 3.3V. The pins above keep each button's
  wires grouped tidily on the header.
- Test the wiring with `python3 test_button.py` from the project root — it
  prints `Button 1 pressed!` / `Button 2 pressed!` on each press.
