import os
import signal
import subprocess
from pathlib import Path
import logging

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PID_FILE = _PROJECT_ROOT / "display.pid"

_DISPLAY_SCRIPTS = {
    "stocks": _PROJECT_ROOT / "display" / "stocks" / "main.py",
    "mta": _PROJECT_ROOT / "display" / "mta" / "main.py",
}


def _kill_running() -> None:
    if not _PID_FILE.exists():
        return
    try:
        pid = int(_PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        log.info(f"Killed display process {pid}")
    except (ProcessLookupError, ValueError):
        pass
    finally:
        _PID_FILE.unlink(missing_ok=True)


def start_display(mode: str) -> int:
    if mode not in _DISPLAY_SCRIPTS:
        raise ValueError(f"Unknown mode: {mode}")

    _kill_running()

    script = _DISPLAY_SCRIPTS[mode]
    proc = subprocess.Popen(
        ["sudo", "python3", str(script)],
        cwd=str(_PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    _PID_FILE.write_text(str(proc.pid))
    log.info(f"Started {mode} display (pid {proc.pid})")
    return proc.pid


def stop_display() -> None:
    _kill_running()


def is_running() -> bool:
    if not _PID_FILE.exists():
        return False
    try:
        pid = int(_PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError, PermissionError):
        return False
