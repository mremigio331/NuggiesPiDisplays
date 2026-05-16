import os
import signal
import subprocess
from pathlib import Path
import logging

from helpers.logger import LOG_DIR

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PID_FILE = _PROJECT_ROOT / "display.pid"

_DISPLAY_SCRIPTS = {
    "stocks": _PROJECT_ROOT / "display" / "stocks" / "main.py",
    "mta": _PROJECT_ROOT / "display" / "mta" / "main.py",
    "clock": _PROJECT_ROOT / "display" / "clock" / "main.py",
    "weather": _PROJECT_ROOT / "display" / "weather" / "main.py",
}

_DISPLAY_LOG = LOG_DIR / "display.log"


def _kill_running() -> None:
    if not _PID_FILE.exists():
        log.debug("No PID file found, nothing to kill")
        return
    try:
        pid = int(_PID_FILE.read_text().strip())
        log.debug(f"Sending SIGTERM to display process {pid}")
        os.kill(pid, signal.SIGTERM)
        log.info(f"Killed display process {pid}")
    except ProcessLookupError:
        log.debug("Process already gone")
    except ValueError:
        log.debug("PID file corrupt, ignoring")
    finally:
        _PID_FILE.unlink(missing_ok=True)


def start_display(mode: str) -> int:
    if mode not in _DISPLAY_SCRIPTS:
        raise ValueError(f"Unknown mode: {mode}")

    log.debug(f"start_display: mode={mode}")
    _kill_running()

    script = _DISPLAY_SCRIPTS[mode]
    log.debug(f"Opening display log at {_DISPLAY_LOG} (append)")
    _DISPLAY_LOG.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(_DISPLAY_LOG, "a")

    env = os.environ.copy()
    display_dir = str(_PROJECT_ROOT / "display")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{display_dir}:{existing}" if existing else display_dir

    log.debug(f"Spawning: sudo python3 {script}")
    proc = subprocess.Popen(
        ["sudo", "python3", str(script)],
        cwd=str(_PROJECT_ROOT),
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
        env=env,
    )
    _PID_FILE.write_text(str(proc.pid))
    log.info(f"Started {mode} display (pid {proc.pid})")
    return proc.pid


def stop_display() -> None:
    log.debug("stop_display called")
    _kill_running()


def is_running() -> bool:
    if not _PID_FILE.exists():
        log.debug("is_running: no PID file")
        return False
    try:
        pid = int(_PID_FILE.read_text().strip())
        os.kill(pid, 0)
        log.debug(f"is_running: pid {pid} alive")
        return True
    except (ProcessLookupError, ValueError, PermissionError):
        log.debug("is_running: pid not alive")
        return False
