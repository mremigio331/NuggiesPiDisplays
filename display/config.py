API_BASE = "http://localhost:8000/api"


def get_brightness(default: int = 100) -> int:
    """Universal LED brightness (1-100) from the API. Falls back to `default`
    if the API is unreachable, so the display never fails to start over a
    brightness read. Called once by each mode's build_matrix() at startup."""
    try:
        import requests

        resp = requests.get(f"{API_BASE}/system/brightness", timeout=3)
        resp.raise_for_status()
        val = int(resp.json().get("brightness", default))
        return max(1, min(100, val))
    except Exception:
        return default
