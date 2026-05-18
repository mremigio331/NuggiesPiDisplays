import logging
import yfinance as yf
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/search")
async def search_stocks(q: str = Query(..., min_length=1, max_length=50)):
    try:
        results = yf.Search(q, max_results=10)
        quotes = [
            {
                "symbol": r.get("symbol", ""),
                "name": r.get("shortname") or r.get("longname") or "",
                "exchange": r.get("exchange", ""),
                "type": r.get("quoteType", ""),
            }
            for r in results.quotes
            if r.get("symbol")
        ]
    except Exception as e:
        logger.error(f"Stock search failed for {q!r}: {e}")
        quotes = []
    return JSONResponse(quotes)
