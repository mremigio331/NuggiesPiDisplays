import logging
import time
from datetime import datetime
import requests
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from helpers.config import read_settings, write_settings

logger = logging.getLogger(__name__)
router = APIRouter()

_cache: dict = {"data": None, "fetched_at": 0.0}
CACHE_TTL = 30 * 60  # 30 minutes

WMO_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Icy fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Rain showers",
    82: "Heavy showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm",
    99: "Thunderstorm",
}


def invalidate_cache() -> None:
    _cache["fetched_at"] = 0.0


def _get_ip_location() -> dict | None:
    try:
        resp = requests.get("http://ip-api.com/json/", timeout=5)
        resp.raise_for_status()
        d = resp.json()
        if d.get("status") == "success":
            city = d.get("city", "")
            region = d.get("regionName", "")
            label = ", ".join(p for p in [city, region] if p)
            return {"latitude": d["lat"], "longitude": d["lon"], "city_label": label}
    except Exception as e:
        logger.warning("IP geolocation failed: %s", e)
    return None


def _fetch_open_meteo(lat: float, lon: float, units: str) -> dict:
    temp_unit = "fahrenheit" if units == "fahrenheit" else "celsius"
    wind_unit = "mph" if units == "fahrenheit" else "kmh"
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m"
        "&hourly=temperature_2m,weather_code"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min"
        f"&temperature_unit={temp_unit}"
        f"&wind_speed_unit={wind_unit}"
        "&timezone=auto"
        "&forecast_days=6"
    )
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _build_response(raw: dict, location: dict, units: str) -> dict:
    current = raw.get("current", {})
    hourly = raw.get("hourly", {})
    daily = raw.get("daily", {})

    wcode = current.get("weather_code", 0)
    current_data = {
        "temperature": round(current.get("temperature_2m", 0)),
        "feels_like": round(current.get("apparent_temperature", 0)),
        "weather_code": wcode,
        "weather_desc": WMO_DESCRIPTIONS.get(wcode, "Unknown"),
        "wind_speed": round(current.get("wind_speed_10m", 0)),
        "units": units,
        "unit_symbol": "°F" if units == "fahrenheit" else "°C",
        "wind_unit": "mph" if units == "fahrenheit" else "km/h",
    }

    # Next 6 hours — consecutive hourly slots starting from the current hour
    current_time_prefix = current.get("time", "")[:13]  # "YYYY-MM-DDTHH"
    times = hourly.get("time", [])
    h_temps = hourly.get("temperature_2m", [])
    h_codes = hourly.get("weather_code", [])

    start_idx = 0
    for i, t in enumerate(times):
        if t[:13] >= current_time_prefix:
            start_idx = i
            break

    hourly_data = []
    for step in range(6):
        idx = start_idx + step
        if idx >= len(times):
            break
        t = times[idx]
        hour_num = int(t[11:13])
        ampm = "A" if hour_num < 12 else "P"
        display_h = hour_num % 12 or 12
        label = "Now" if step == 0 else f"{display_h}{ampm}"
        hourly_data.append(
            {
                "time": t,
                "time_label": label,
                "temperature": round(h_temps[idx]) if idx < len(h_temps) else 0,
                "weather_code": h_codes[idx] if idx < len(h_codes) else 0,
            }
        )

    # 5-day daily forecast
    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    d_dates = daily.get("time", [])
    d_codes = daily.get("weather_code", [])
    d_max = daily.get("temperature_2m_max", [])
    d_min = daily.get("temperature_2m_min", [])

    daily_data = []
    for i in range(min(5, len(d_dates))):
        dt = datetime.strptime(d_dates[i], "%Y-%m-%d")
        daily_data.append(
            {
                "date": d_dates[i],
                "day_label": DAYS[dt.weekday()],
                "weather_code": d_codes[i] if i < len(d_codes) else 0,
                "temp_max": round(d_max[i]) if i < len(d_max) else 0,
                "temp_min": round(d_min[i]) if i < len(d_min) else 0,
            }
        )

    return {
        "location": location,
        "current": current_data,
        "hourly": hourly_data,
        "daily": daily_data,
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/data")
async def get_weather_data(force: bool = False):
    now = time.time()

    if not force and _cache["data"] and (now - _cache["fetched_at"]) < CACHE_TTL:
        return JSONResponse(_cache["data"])

    settings = read_settings()
    weather_cfg = settings.get("weather", {})
    units = weather_cfg.get("units", "fahrenheit")
    lat = weather_cfg.get("latitude")
    lon = weather_cfg.get("longitude")
    city_label = weather_cfg.get("city_label", "")

    if lat is None or lon is None or weather_cfg.get("use_ip_location", True):
        ip_loc = _get_ip_location()
        if ip_loc:
            lat = ip_loc["latitude"]
            lon = ip_loc["longitude"]
            if not city_label or weather_cfg.get("use_ip_location", True):
                city_label = ip_loc.get("city_label", "")
            # Persist detected location so display process can read it
            weather_cfg["latitude"] = lat
            weather_cfg["longitude"] = lon
            weather_cfg["city_label"] = city_label
            settings["weather"] = weather_cfg
            write_settings(settings)
        elif lat is None or lon is None:
            if _cache["data"]:
                return JSONResponse(_cache["data"])
            return JSONResponse(
                {"error": "Could not determine location"}, status_code=503
            )

    location = {"latitude": lat, "longitude": lon, "city_label": city_label}

    try:
        raw = _fetch_open_meteo(lat, lon, units)
        data = _build_response(raw, location, units)
        _cache["data"] = data
        _cache["fetched_at"] = now
        return JSONResponse(data)
    except Exception as e:
        logger.error("Weather fetch failed: %s", e)
        if _cache["data"]:
            return JSONResponse(_cache["data"])
        return JSONResponse({"error": str(e)}, status_code=503)
