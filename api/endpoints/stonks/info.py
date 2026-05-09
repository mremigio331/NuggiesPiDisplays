import logging
import yfinance as yf
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{symbol}/info")
async def get_stock_info(symbol: str):
    symbol = symbol.upper()
    try:
        results = yf.Search(symbol, max_results=5)
        quote = next(
            (q for q in results.quotes if q.get("symbol", "").upper() == symbol),
            results.quotes[0] if results.quotes else {},
        )
        name = quote.get("shortname") or quote.get("longname") or symbol
        exchange = quote.get("exchange", "")
    except Exception as e:
        logger.warning("Could not fetch info for %s: %s", symbol, e)
        name = symbol
        exchange = ""
    return JSONResponse({"symbol": symbol, "name": name, "exchange": exchange})
