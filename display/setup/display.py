import os
import sys
import time
from pathlib import Path

_FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"

HEADLESS = os.environ.get("HEADLESS", "false").lower() == "true"


def _load_font(graphics, path):
    f = graphics.Font()
    try:
        f.LoadFont(str(path))
        print(f"Loaded font: {path}", flush=True)
    except Exception as e:
        print(f"Could not load font {path}: {e}", file=sys.stderr, flush=True)
    return f


def run(ssid: str, password: str):
    try:
        if HEADLESS:
            raise ImportError("headless")
        from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
    except Exception as e:
        print(f"Setup display init failed: {e}", file=sys.stderr, flush=True)
        while True:
            time.sleep(60)

    font_sm = _load_font(graphics, _FONTS_DIR / "4x6.bdf")
    font_lg = _load_font(graphics, _FONTS_DIR / "5x8.bdf")

    try:
        options = RGBMatrixOptions()
        options.rows = 32
        options.cols = 64
        options.chain_length = 1
        options.parallel = 1
        options.hardware_mapping = "adafruit-hat"
        options.gpio_slowdown = 2
        options.pwm_lsb_nanoseconds = 200
        matrix = RGBMatrix(options=options)
    except Exception as e:
        print(f"Matrix init failed: {e}", file=sys.stderr, flush=True)
        while True:
            time.sleep(60)

    cyan = graphics.Color(0, 200, 255)
    white = graphics.Color(255, 255, 255)
    yellow = graphics.Color(255, 200, 0)

    canvas = matrix.CreateFrameCanvas()
    canvas.Clear()

    graphics.DrawText(canvas, font_lg, 4, 9, cyan, "WiFi Setup")
    graphics.DrawLine(canvas, 0, 11, 63, 11, graphics.Color(40, 40, 40))
    graphics.DrawText(canvas, font_sm, 2, 20, white, ssid)
    graphics.DrawText(canvas, font_sm, 2, 29, yellow, f"PW:{password}")

    matrix.SwapOnVSync(canvas)

    while True:
        time.sleep(60)
