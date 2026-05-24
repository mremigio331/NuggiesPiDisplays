import asyncio
import logging
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from helpers.process import _PROJECT_ROOT

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 3600  # 1 hour


@dataclass
class UpdateStatus:
    update_available: bool = False
    commits_behind: int = 0
    current_sha: str = ""
    latest_sha: str = ""
    branch: str = ""
    last_checked: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "update_available": self.update_available,
            "commits_behind": self.commits_behind,
            "current_sha": self.current_sha,
            "latest_sha": self.latest_sha,
            "branch": self.branch,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "error": self.error,
        }


_status = UpdateStatus()
_lock = threading.Lock()


def get_status() -> UpdateStatus:
    with _lock:
        return _status


def _fetch_and_compare() -> UpdateStatus:
    """Blocking — run in a thread executor."""
    try:
        subprocess.run(
            ["git", "-C", str(_PROJECT_ROOT), "fetch", "origin"],
            capture_output=True,
            timeout=15,
        )
    except Exception as e:
        logger.warning(f"git fetch failed: {e}")
        return UpdateStatus(error=str(e), last_checked=datetime.now(timezone.utc))

    def _rev(ref: str) -> str:
        r = subprocess.run(
            ["git", "-C", str(_PROJECT_ROOT), "rev-parse", ref],
            capture_output=True, text=True,
        )
        return r.stdout.strip()

    def _count(range_: str) -> int:
        r = subprocess.run(
            ["git", "-C", str(_PROJECT_ROOT), "rev-list", range_, "--count"],
            capture_output=True, text=True,
        )
        try:
            return int(r.stdout.strip())
        except ValueError:
            return 0

    branch = subprocess.run(
        ["git", "-C", str(_PROJECT_ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()

    local = _rev("HEAD")
    remote = _rev(f"origin/{branch}")

    if not local or not remote:
        return UpdateStatus(
            error="Could not resolve git refs",
            last_checked=datetime.now(timezone.utc),
        )

    commits_behind = _count(f"HEAD..origin/{branch}")
    logger.info(f"Update check: branch={branch} behind={commits_behind}")
    return UpdateStatus(
        update_available=commits_behind > 0,
        commits_behind=commits_behind,
        current_sha=local[:7],
        latest_sha=remote[:7],
        branch=branch,
        last_checked=datetime.now(timezone.utc),
    )


async def refresh() -> UpdateStatus:
    """Run a git fetch and update the cache. Awaitable."""
    global _status
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _fetch_and_compare)
    with _lock:
        _status = result
    return result


async def run_background_checker() -> None:
    """Check on startup then every hour."""
    while True:
        await refresh()
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
