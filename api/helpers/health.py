"""Device health: live stats plus a heat log sampled every 10 minutes.

``snapshot()`` reads the Pi's current numbers (CPU temp, CPU use, memory, disk,
uptime, throttle flags) straight from /proc, /sys and vcgencmd. Every read is
best-effort: a missing source gives None instead of raising, so the endpoint
still answers on a box without vcgencmd or a thermal zone.

``run_health_logger()`` is a background task in the API lifespan. Every
``SAMPLE_SECONDS`` it appends one JSON line to ``HEALTH_LOG`` and keeps the
last ``KEEP_SAMPLES`` (7 days). One small append per 10 minutes is light on
the SD card; the file is only rewritten when it grows past twice the cap.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

HEALTH_LOG = Path(__file__).resolve().parent.parent / "data" / "health.jsonl"
SAMPLE_SECONDS = 600
KEEP_SAMPLES = 7 * 24 * 6  # 7 days at one sample per 10 minutes
THERMAL_ZONE = Path("/sys/class/thermal/thermal_zone0/temp")

# Bits of `vcgencmd get_throttled`. Low bits are "happening now", the 1<<16+
# bits are "has happened since boot".
THROTTLE_FLAGS = {
    0: "under_voltage",
    1: "freq_capped",
    2: "throttled",
    3: "soft_temp_limit",
    16: "under_voltage_since_boot",
    17: "freq_capped_since_boot",
    18: "throttled_since_boot",
    19: "soft_temp_limit_since_boot",
}


def read_temp_c() -> float | None:
    try:
        return round(int(THERMAL_ZONE.read_text().strip()) / 1000, 1)
    except (OSError, ValueError):
        return None


def read_throttled() -> dict | None:
    try:
        out = subprocess.run(
            ["vcgencmd", "get_throttled"],
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        value = int(out.split("=", 1)[1], 16)
    except (OSError, IndexError, ValueError, subprocess.SubprocessError):
        return None
    return {
        "raw": hex(value),
        "flags": [name for bit, name in THROTTLE_FLAGS.items() if value & (1 << bit)],
    }


def _cpu_times() -> tuple[int, int] | None:
    """(idle, total) jiffies across all CPUs from the first line of /proc/stat."""
    try:
        fields = [
            int(x) for x in Path("/proc/stat").read_text().split("\n", 1)[0].split()[1:]
        ]
    except (OSError, ValueError):
        return None
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
    return idle, sum(fields)


def cpu_percent(
    before: tuple[int, int] | None, after: tuple[int, int] | None
) -> float | None:
    if not before or not after:
        return None
    total = after[1] - before[1]
    if total <= 0:
        return None
    return round(100 * (1 - (after[0] - before[0]) / total), 1)


def read_memory() -> dict | None:
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, rest = line.split(":", 1)
            info[key] = int(rest.split()[0])  # kB
        total = info["MemTotal"]
        available = info["MemAvailable"]
    except (OSError, KeyError, ValueError):
        return None
    used = total - available
    return {
        "total_mb": round(total / 1024),
        "used_mb": round(used / 1024),
        "percent": round(100 * used / total, 1),
    }


def read_disk() -> dict | None:
    try:
        usage = shutil.disk_usage("/")
    except OSError:
        return None
    return {
        "total_gb": round(usage.total / 1e9, 1),
        "used_gb": round(usage.used / 1e9, 1),
        "percent": round(100 * usage.used / usage.total, 1),
    }


def read_uptime_seconds() -> int | None:
    try:
        return int(float(Path("/proc/uptime").read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        return None


def read_load() -> list[float] | None:
    try:
        return [round(x, 2) for x in os.getloadavg()]
    except OSError:
        return None


async def snapshot() -> dict:
    """Current device stats. CPU use is measured over a short half-second window."""
    before = _cpu_times()
    await asyncio.sleep(0.5)
    after = _cpu_times()
    return {
        "time": int(time.time()),
        "temp_c": read_temp_c(),
        "cpu_percent": cpu_percent(before, after),
        "cpu_count": os.cpu_count(),
        "load": read_load(),
        "memory": read_memory(),
        "disk": read_disk(),
        "uptime_seconds": read_uptime_seconds(),
        "throttled": read_throttled(),
    }


def read_history(hours: float | None = None) -> list[dict]:
    """Logged samples, oldest first, optionally only the last ``hours``."""
    try:
        lines = HEALTH_LOG.read_text().splitlines()
    except OSError:
        return []
    cutoff = time.time() - hours * 3600 if hours else 0
    samples = []
    for line in lines:
        try:
            sample = json.loads(line)
        except ValueError:
            continue  # a line cut short by power loss
        if sample.get("t", 0) >= cutoff:
            samples.append(sample)
    return samples


def _append_sample(sample: dict) -> None:
    HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with HEALTH_LOG.open("a") as f:
        f.write(json.dumps(sample, separators=(",", ":")) + "\n")
    # Trim only once the file holds twice the cap, so most samples are a
    # single append rather than a full rewrite.
    samples = read_history()
    if len(samples) > 2 * KEEP_SAMPLES:
        tmp = HEALTH_LOG.with_suffix(".tmp")
        tmp.write_text(
            "".join(
                json.dumps(s, separators=(",", ":")) + "\n"
                for s in samples[-KEEP_SAMPLES:]
            )
        )
        tmp.replace(HEALTH_LOG)


async def run_health_logger() -> None:
    """Background loop: log temp, CPU use (averaged over the interval) and memory."""
    logger.info("Health logger started (every %ss -> %s)", SAMPLE_SECONDS, HEALTH_LOG)
    before = _cpu_times()
    while True:
        await asyncio.sleep(SAMPLE_SECONDS)
        try:
            after = _cpu_times()
            memory = read_memory()
            throttled = read_throttled()
            sample = {
                "t": int(time.time()),
                "temp": read_temp_c(),
                "cpu": cpu_percent(before, after),
                "mem": memory["percent"] if memory else None,
                "throttled": throttled["raw"] if throttled else None,
            }
            before = after
            await asyncio.to_thread(_append_sample, sample)
            logger.debug("Health sample: %s", sample)
        except Exception:
            logger.exception("Health logger tick failed (continuing)")
