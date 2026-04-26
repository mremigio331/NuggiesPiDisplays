import logging
import time
import api_client
import renderer
from matrix import build_matrix

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_INTERVAL = 60
CYCLE_SECONDS = 5


def _build_queue(settings: dict) -> list[dict]:
    symbols = settings.get("stock_abbrs", [])
    cycles = [c for c in settings.get("stock_cycles", []) if c.get("enabled")]
    return [{"symbol": s, "cycle_key": c["key"]} for s in symbols for c in cycles]


def _display_item(matrix, canvas, data: dict, interval: int):
    start = time.time()
    show_pct = True
    while time.time() - start < interval:
        renderer.render(canvas, data, show_pct=show_pct)
        canvas = matrix.SwapOnVSync(canvas)
        time.sleep(CYCLE_SECONDS)
        show_pct = not show_pct
    return canvas


def run():
    matrix = build_matrix()
    canvas = matrix.CreateFrameCanvas()
    logger.info("Stocks display starting")

    while True:
        settings = api_client.get_settings() or {}
        queue = _build_queue(settings)
        interval = settings.get("interval_seconds", DEFAULT_INTERVAL)

        if not queue:
            logger.warning("No stocks/cycles configured, retrying in 30s")
            time.sleep(30)
            continue

        for item in queue:
            symbol, cycle_key = item["symbol"], item["cycle_key"]
            logger.info("Fetching %s/%s", symbol, cycle_key)
            data = api_client.get_stock_chart(symbol, cycle_key)
            if data is None:
                logger.warning("No data for %s/%s, skipping", symbol, cycle_key)
                continue
            logger.info("Showing %s/%s for %ss", symbol, cycle_key, interval)
            canvas = _display_item(matrix, canvas, data, interval)


if __name__ == "__main__":
    run()
