"""Shared path constants for WiFi state flags written by the API and read by the boot service."""

from helpers.process import _PROJECT_ROOT

WIFI_FLAG = _PROJECT_ROOT / ".wifi_configured"
FORCE_PORTAL = _PROJECT_ROOT / ".force_portal"
