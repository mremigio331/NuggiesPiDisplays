import logging
import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/geocode")
async def geocode(q: str):
    """Search for a location by city name using OpenStreetMap Nominatim."""
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 5},
            headers={"User-Agent": "NuggiesPiDisplays/1.0 (personal-rpi-project)"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
        return JSONResponse(
            [
                {
                    "display_name": r["display_name"],
                    "short_name": r["display_name"].split(",")[0].strip(),
                    "latitude": float(r["lat"]),
                    "longitude": float(r["lon"]),
                }
                for r in results
            ]
        )
    except Exception as e:
        logger.error("Geocode failed: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
