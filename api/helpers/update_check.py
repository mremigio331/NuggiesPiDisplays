import asyncio
import logging
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from helpers.process import _PROJECT_ROOT

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 3600  # 1 hour

# Which repo paths belong to each updatable component. Mirrors the skip-if-
# unchanged checks in setup.sh so the UI's per-component "behind" signal and the
# script's "did it change?" decision agree. Keep these two in sync.
COMPONENT_PATHS: dict[str, list[str]] = {
    "website": ["website/"],
    "api": ["api/", "requirements-api.txt"],
    "display": ["display/", "requirements-display.txt"],
    "system": ["setup.sh", "scripts/"],
}


@dataclass
class UpdateStatus:
    update_available: bool = False
    commits_behind: int = 0
    current_sha: str = ""
    latest_sha: str = ""
    branch: str = ""
    # Which release stage this device tracks ("beta"|"prod").
    stage: str = "prod"
    # Subject lines of the pending commits (newest first), so the UI can show
    # the user what an update will actually change before they install it.
    commits: list[str] = field(default_factory=list)
    # Per-component breakdown: {component: {"behind": int, "commits": [str]}}.
    # Lets the UI light up only the parts that actually changed and offer a
    # scoped update for each. The top-level fields above stay authoritative for
    # "is ANY update available" so older clients keep working unchanged.
    components: dict = field(default_factory=dict)
    last_checked: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "update_available": self.update_available,
            "commits_behind": self.commits_behind,
            "current_sha": self.current_sha,
            "latest_sha": self.latest_sha,
            "branch": self.branch,
            "stage": self.stage,
            "commits": self.commits,
            "components": self.components,
            "last_checked": (
                self.last_checked.isoformat() if self.last_checked else None
            ),
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
            ["git", "-C", str(_PROJECT_ROOT), "fetch", "origin", "--tags", "--force"],
            capture_output=True,
            timeout=15,
        )
    except Exception as e:
        logger.warning(f"git fetch failed: {e}")
        return UpdateStatus(error=str(e), last_checked=datetime.now(timezone.utc))

    def _rev(ref: str) -> str:
        r = subprocess.run(
            ["git", "-C", str(_PROJECT_ROOT), "rev-parse", ref],
            capture_output=True,
            text=True,
        )
        return r.stdout.strip()

    def _count(range_: str) -> int:
        r = subprocess.run(
            ["git", "-C", str(_PROJECT_ROOT), "rev-list", range_, "--count"],
            capture_output=True,
            text=True,
        )
        try:
            return int(r.stdout.strip())
        except ValueError:
            return 0

    def _commit_subjects(
        range_: str, limit: int = 50, paths: list[str] | None = None
    ) -> list[str]:
        """Subject lines of commits in *range_*, newest first (capped at *limit*).

        When *paths* is given, only commits that touched those paths count — this
        is how the per-component "what changed" list is built.
        """
        cmd = [
            "git",
            "-C",
            str(_PROJECT_ROOT),
            "log",
            range_,
            f"--max-count={limit}",
            "--pretty=format:%s",
        ]
        if paths:
            cmd += ["--", *paths]
        r = subprocess.run(cmd, capture_output=True, text=True)
        return [line for line in r.stdout.splitlines() if line.strip()]

    branch = subprocess.run(
        ["git", "-C", str(_PROJECT_ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()

    # Devices track a release STAGE TAG (beta/prod), not a branch. Compare HEAD
    # against that tag so "update available" reflects the stream the user opted
    # into. Fall back to origin/<branch> for a dev checkout that is still on a
    # real branch and has no stage tag yet.
    try:
        from helpers.config import read_update_stage

        stage = read_update_stage()
    except Exception:
        stage = "prod"

    target_ref = f"refs/tags/{stage}"
    if not _rev(target_ref):
        # No stage tag locally (fresh clone / CI hasn't published). Fall back to
        # the tracked branch so the check still returns something sensible.
        target_ref = (
            f"origin/{branch}" if branch and branch != "HEAD" else "origin/main"
        )

    local = _rev("HEAD")
    remote = _rev(target_ref)

    if not local or not remote:
        return UpdateStatus(
            error="Could not resolve git refs",
            last_checked=datetime.now(timezone.utc),
        )

    range_ = f"HEAD..{target_ref}"
    commits_behind = _count(range_)
    commits = _commit_subjects(range_) if commits_behind > 0 else []

    # Per-component breakdown: for each component, the commits in the pending
    # range that touched its paths. behind = len(those commits). A component
    # with behind == 0 did not change and the UI can mark it up to date.
    components: dict = {}
    for name, paths in COMPONENT_PATHS.items():
        c = _commit_subjects(range_, paths=paths) if commits_behind > 0 else []
        components[name] = {"behind": len(c), "commits": c}

    logger.info(
        "Update check: stage=%s target=%s behind=%s components=%s",
        stage,
        target_ref,
        commits_behind,
        {k: v["behind"] for k, v in components.items()},
    )
    return UpdateStatus(
        update_available=commits_behind > 0,
        commits_behind=commits_behind,
        current_sha=local[:7],
        latest_sha=remote[:7],
        branch=branch,
        stage=stage,
        commits=commits,
        components=components,
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
