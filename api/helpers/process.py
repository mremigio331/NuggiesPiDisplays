import os
import subprocess
import time
from pathlib import Path
import logging

from helpers.logger import LOG_DIR

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PID_FILE = _PROJECT_ROOT / "display.pid"

_DISPLAY_SCRIPTS = {
    "clock": _PROJECT_ROOT / "display" / "clock" / "main.py",
    "mta": _PROJECT_ROOT / "display" / "mta" / "main.py",
    "sports": _PROJECT_ROOT / "display" / "sports" / "main.py",
    "stocks": _PROJECT_ROOT / "display" / "stocks" / "main.py",
    "weather": _PROJECT_ROOT / "display" / "weather" / "main.py",
}

_DISPLAY_LOG = LOG_DIR / "display.log"


def _privileged_command(*args: str) -> list[str]:
    # If the API itself is running as root, do not shell out through sudo.
    if os.geteuid() == 0:
        return list(args)
    # -n prevents sudo from prompting for a password in a non-interactive API context.
    return ["sudo", "-n", *args]


def _wait_pid_exit(pid: int, timeout: float = 2.0) -> bool:
    """Poll until *pid* is gone or *timeout* expires. Returns True if process exited."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            os.kill(pid, 0)  # probe — raises if gone
        except (ProcessLookupError, PermissionError):
            return True
        time.sleep(0.05)
    return False


def _kill_running() -> None:
    if _PID_FILE.exists():
        try:
            pid = int(_PID_FILE.read_text().strip())
            # Display processes run as root via sudo, so use sudo kill
            result = subprocess.run(
                _privileged_command("kill", "-TERM", str(pid)),
                capture_output=True,
            )
            if result.returncode == 0:
                log.info(f"Sent SIGTERM to display process {pid}")
                # Wait for the process to actually exit before continuing
                if not _wait_pid_exit(pid):
                    log.warning(
                        f"Process {pid} did not exit after SIGTERM, sending SIGKILL"
                    )
                    subprocess.run(
                        _privileged_command("kill", "-KILL", str(pid)),
                        capture_output=True,
                    )
                    _wait_pid_exit(pid, timeout=1.0)
            else:
                log.debug(
                    f"kill {pid} returned {result.returncode}: {result.stderr.decode().strip()}"
                )
        except ValueError:
            log.debug("PID file corrupt, ignoring")
        finally:
            _PID_FILE.unlink(missing_ok=True)

    # Sweep any orphaned display processes regardless of PID file state.
    # Use SIGKILL directly — these processes hold the LED matrix and must die immediately.
    sweep = subprocess.run(
        _privileged_command("pkill", "-KILL", "-f", r"display/.*/main\.py"),
        capture_output=True,
    )
    # pkill returns 1 when no process matches; that is not an error.
    if sweep.returncode not in (0, 1):
        log.warning(
            f"pkill sweep failed ({sweep.returncode}): {sweep.stderr.decode().strip()}"
        )

    # Brief pause to let the kernel fully reap killed processes before starting the new one
    time.sleep(0.15)
    log.debug("pkill sweep complete")


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

    cmd = _privileged_command("python3", str(script))
    log.debug(f"Spawning: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=str(_PROJECT_ROOT),
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
        env=env,
    )

    # Fail fast when sudo policy denies execution, instead of returning a dead PID.
    time.sleep(0.25)
    exit_code = proc.poll()
    if exit_code is not None:
        raise RuntimeError(
            "Failed to start display process. Verify passwordless sudo policy for display scripts "
            "(try: sudo bash setup.sh --update)."
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
        status_path = Path(f"/proc/{pid}/status")
        if status_path.exists():
            for line in status_path.read_text().splitlines():
                if line.startswith("State:") and "Z" in line:
                    log.debug(f"is_running: pid {pid} is zombie, treating as dead")
                    _PID_FILE.unlink(missing_ok=True)
                    return False
        log.debug(f"is_running: pid {pid} alive")
        return True
    except (ProcessLookupError, ValueError, PermissionError):
        log.debug("is_running: pid not alive")
        return False
