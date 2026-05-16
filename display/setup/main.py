#!/usr/bin/env python3
"""
Runs during WiFi captive portal mode.
Scrolls the AP credentials on the matrix so the user knows how to connect.
"""

import os
import time
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_cfg = yaml.safe_load((_PROJECT_ROOT / "wifi_ap.yaml").read_text())
AP_SSID = _cfg["ssid"]
AP_PASSWORD = _cfg["password"]

_FONT_SM = Path(__file__).parent.parent / "fonts" / "4x6.bdf"
_FONT_LG = Path(__file__).parent.parent / "fonts" / "5x8.bdf"

HEADLESS = os.environ.get("HEADLESS", "false").lower() == "true"


def run():
    try:
        if HEADLESS:
            raise ImportError("headless")
        from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics

        options = RGBMatrixOptions()
        options.rows = 32
        options.cols = 64
        options.chain_length = 1
        options.parallel = 1
        options.hardware_mapping = "adafruit-hat"
        matrix = RGBMatrix(options=options)
    except ImportError:
        while True:
            time.sleep(60)

    font_sm = graphics.Font()
    font_lg = graphics.Font()
    if _FONT_SM.exists():
        font_sm.LoadFont(str(_FONT_SM))
    if _FONT_LG.exists():
        font_lg.LoadFont(str(_FONT_LG))

    cyan = graphics.Color(0, 200, 255)
    white = graphics.Color(255, 255, 255)
    yellow = graphics.Color(255, 200, 0)

    # Scroll the two credential lines; header stays static
    ssid_text = f"  {AP_SSID}  "
    pw_text = f"  PW: {AP_PASSWORD}  "

    # Rough char width for 4x6 font is ~5px
    CHAR_W = 5
    ssid_px = len(ssid_text) * CHAR_W
    pw_px = len(pw_text) * CHAR_W

    ssid_x = 64
    pw_x = 64 + 30  # stagger so they're not in sync

    canvas = matrix.CreateFrameCanvas()

    while True:
        canvas.Clear()

        # Static header
        graphics.DrawText(canvas, font_lg, 4, 9, cyan, "WiFi Setup")

        # Divider line
        graphics.DrawLine(canvas, 0, 11, 63, 11, graphics.Color(40, 40, 40))

        # Scrolling SSID
        graphics.DrawText(canvas, font_sm, ssid_x, 20, white, ssid_text)

        # Scrolling password
        graphics.DrawText(canvas, font_sm, pw_x, 29, yellow, pw_text)

        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(0.04)

        ssid_x -= 1
        pw_x -= 1

        if ssid_x < -ssid_px:
            ssid_x = 64
        if pw_x < -pw_px:
            pw_x = 64


if __name__ == "__main__":
    run()
