from __future__ import annotations

import subprocess
import time
from pathlib import Path

WIFI_FLAG = Path(__file__).parent.parent / ".wifi_configured"
AP_SSID = "NuggiesSetup"
AP_CON_NAME = "NuggiesHotspot"
AP_IP = "10.42.0.1"


def is_connected() -> bool:
    """Return True if NM reports full or limited internet connectivity."""
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "CONNECTIVITY", "general"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        state = result.stdout.strip().lower()
        return state in ("full", "limited")
    except Exception:
        return False


def scan_networks() -> list[dict]:
    """Return a sorted list of visible WiFi networks (excludes the setup AP)."""
    try:
        subprocess.run(
            ["nmcli", "device", "wifi", "rescan"],
            capture_output=True,
            timeout=15,
        )
        time.sleep(2)

        result = subprocess.run(
            [
                "nmcli",
                "--escape",
                "no",
                "-t",
                "-f",
                "SSID,SIGNAL,SECURITY",
                "device",
                "wifi",
                "list",
                "--rescan",
                "no",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return []

    networks: list[dict] = []
    seen: set[str] = set()

    for line in result.stdout.strip().splitlines():
        # rsplit from the right: SIGNAL and SECURITY are always the last two fields.
        # This correctly handles SSIDs that contain colons.
        parts = line.rsplit(":", 2)
        if len(parts) != 3:
            continue
        ssid, signal_str, security = parts
        ssid = ssid.strip()
        if not ssid or ssid == AP_SSID or ssid in seen:
            continue
        seen.add(ssid)
        try:
            signal = int(signal_str)
        except ValueError:
            signal = 0
        networks.append(
            {
                "ssid": ssid,
                "signal": signal,
                "secured": security.strip() not in ("", "--"),
            }
        )

    return sorted(networks, key=lambda n: -n["signal"])


def connect_to_network(ssid: str, password: str | None) -> dict:
    """Attempt to connect wlan0 to the given SSID. Blocks until done or failed."""
    cmd = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        cmd += ["password", password]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Connection timed out — check the password and try again.",
        }
    except Exception as exc:
        return {"success": False, "message": str(exc)}

    if result.returncode == 0:
        WIFI_FLAG.touch()
        return {"success": True, "message": "Connected successfully."}

    error = (result.stderr or result.stdout).strip()
    return {"success": False, "message": error or "Connection failed."}


def start_hotspot() -> bool:
    """Start the NuggiesSetup open-access AP via NetworkManager."""
    try:
        result = subprocess.run(
            [
                "nmcli",
                "device",
                "wifi",
                "hotspot",
                "ifname",
                "wlan0",
                "ssid",
                AP_SSID,
                "con-name",
                AP_CON_NAME,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def stop_hotspot() -> None:
    subprocess.run(
        ["nmcli", "connection", "delete", AP_CON_NAME],
        capture_output=True,
        timeout=10,
    )
