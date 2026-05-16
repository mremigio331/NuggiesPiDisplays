import logging
import math
import yfinance
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from helpers.config import read_settings


def _f(v):
    """Return None for NaN/None, otherwise the float value."""
    if v is None:
        return None
    try:
        return None if math.isnan(v) else v
    except TypeError:
        return None


logger = logging.getLogger(__name__)
router = APIRouter()

CYCLE_PARAMS = {
    "intraday": {"period": "1d", "interval": "5m"},
    "6month": {"period": "6mo", "interval": "1d"},
    "ytd": {"period": "ytd", "interval": "1d"},
    "1year": {"period": "1y", "interval": "1d"},
}


@router.get("/{symbol}/{cycle_key}")
async def get_stock_chart(symbol: str, cycle_key: str):
    symbol = symbol.upper()
    if cycle_key not in CYCLE_PARAMS:
        raise HTTPException(
            status_code=400, detail=f"cycle_key must be one of {list(CYCLE_PARAMS)}"
        )

    settings = read_settings()
    cycles = settings.get("stocks", {}).get("stock_cycles", [])
    cycle_cfg = next((c for c in cycles if c["key"] == cycle_key), None)
    label = cycle_cfg["label"] if cycle_cfg else cycle_key

    params = CYCLE_PARAMS[cycle_key]
    logger.info(
        "Fetching %s/%s period=%s interval=%s",
        symbol,
        cycle_key,
        params["period"],
        params["interval"],
    )

    try:
        ticker = yfinance.Ticker(symbol)
        hist = ticker.history(period=params["period"], interval=params["interval"])
        current_price = ticker.fast_info.get("last_price")
    except Exception as e:
        logger.exception("Yahoo Finance error for %s/%s", symbol, cycle_key)
        raise HTTPException(status_code=502, detail=f"Yahoo Finance error: {e}")

    if hist.empty:
        logger.warning("%s/%s history is empty", symbol, cycle_key)
        return JSONResponse(
            {
                "symbol": symbol,
                "label": label,
                "current_price": None,
                "change": None,
                "change_pct": None,
                "direction": None,
                "closes": [],
                "timestamps": [],
            }
        )

    if current_price is None:
        current_price = _f(float(hist["Close"].iloc[-1]))

    current_price = _f(current_price)
    closes = [_f(round(float(c), 4)) for c in hist["Close"].tolist()]
    open_price = next((c for c in closes if c is not None), None)
    change = (
        round(current_price - open_price, 4)
        if current_price is not None and open_price
        else None
    )
    change_pct = (
        round((change / open_price) * 100, 2)
        if change is not None and open_price
        else None
    )

    return JSONResponse(
        {
            "symbol": symbol,
            "label": label,
            "current_price": (
                round(current_price, 4) if current_price is not None else None
            ),
            "change": change,
            "change_pct": change_pct,
            "direction": (
                ("up" if change >= 0 else "down") if change is not None else None
            ),
            "closes": closes,
            "timestamps": hist.index.strftime("%Y-%m-%dT%H:%M:%S").tolist(),
        }
    )
