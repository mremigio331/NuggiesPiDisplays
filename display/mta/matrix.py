import os

HEADLESS = os.environ.get("HEADLESS", "false").lower() == "true"
USING_HARDWARE = False

try:
    if HEADLESS:
        raise ImportError("headless mode")
    from rgbmatrix import RGBMatrix, RGBMatrixOptions

    USING_HARDWARE = True

    def build_matrix() -> RGBMatrix:
        options = RGBMatrixOptions()
        options.rows = 32
        options.cols = 64
        options.chain_length = 1
        options.parallel = 1
        options.hardware_mapping = "adafruit-hat"
        options.gpio_slowdown = 2
        options.pwm_lsb_nanoseconds = 200
        return RGBMatrix(options=options)

except ImportError:

    class _MockCanvas:
        def Clear(self):
            pass

        def SetPixel(self, x, y, r, g, b):
            pass

    class _MockMatrix:
        def CreateFrameCanvas(self):
            return _MockCanvas()

        def SwapOnVSync(self, canvas):
            return canvas

    def build_matrix():
        return _MockMatrix()
