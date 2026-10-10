import asyncio
import logging
import os
import shutil
import subprocess

from helpers.config import (
    read_settings as _read_settings,
    reset_settings as _reset_settings,
)
from helpers.dev_config import is_dev_mode
from helpers.logger import LOG_DIR
from helpers.process import (
    _PROJECT_ROOT,
    start_display as _start_display,
    stop_display as _stop_display,
)
from helpers.wifi_state import FORCE_PORTAL, WIFI_FLAG

# Importing `helpers.wifi_state` above inserts the project root onto sys.path, so the
# shared resolver package is importable from the api-rooted working directory. Clear the
# `.wifi_configured` cache through the resolver so the marker semantics stay owned by the
# single source of truth (wifi_setup/wifi_state.py) rather than duplicated here.
from wifi_setup.wifi_state import clear_configured as _clear_configured

logger = logging.getLogger(__name__)

_FACTORY_WIFI_RESET = _PROJECT_ROOT / ".factory_wifi_reset"

# Sentinel written as the first line of update.log at the start of each setup.sh
# run. The /system/update-log endpoint and the UI use it to recognise a fresh
# run. Keep in sync with any client-side check.
_UPDATE_LOG_START = "=== NUGGIES UPDATE START ==="


def _privileged_command(*args: str) -> list[str]:
    # If already root (e.g., service user), run command directly.
    if os.geteuid() == 0:
        return list(args)
    # Resolve the target binary to an absolute path. The sudoers grants written
    # by setup.sh (setup_sudoers) use absolute interpreter/command paths
    # ($BASH, $PYTHON, $REBOOT, $SYSTEMCTL, $CHMOD, ...). sudo matches the
    # invoked command against those exact paths, and in the API's
    # non-interactive environment a BARE command name (e.g. `bash`) does NOT
    # match the absolute-path grant — `sudo -n` is then refused with
    # "a password is required" and the privileged action silently never runs
    # (this is what broke web-UI updates). Resolving to the absolute path here
    # makes every call match the grant regardless of sudo's secure_path.
    resolved = list(args)
    if resolved:
        abs_path = shutil.which(resolved[0])
        if abs_path:
            resolved[0] = abs_path
    # -n prevents hanging on password prompts in HTTP request handlers.
    return ["sudo", "-n", *resolved]


class SystemManager:
    def reboot(self) -> None:
        logger.info("Rebooting Pi")
        result = subprocess.run(_privileged_command("reboot"), capture_output=True)
        if result.returncode != 0:
            err = result.stderr.decode().strip()
            logger.error(f"Reboot failed: {err}")
            raise RuntimeError(f"Reboot failed: {err}")

    def wifi_service_restart(self) -> None:
        subprocess.Popen(
            _privileged_command("systemctl", "restart", "nuggies-wifi-setup.service"),
        )

    def stop_display(self) -> None:
        try:
            _stop_display()
            logger.info("Display stopped")
        except Exception as e:
            logger.warning(f"Could not stop display (continuing): {e}")

    def reset_settings(self) -> None:
        _reset_settings()
        logger.info("Settings reset to defaults")

    # ------------------------------------------------------------------ #
    # setup.sh runner
    # ------------------------------------------------------------------ #
    def _run_setup_detached(self, *flags: str) -> None:
        """Run setup.sh DETACHED from the API's process group, logging to a file.

        setup.sh (both --update and the full installer) restarts
        nuggies-api.service. When setup.sh runs as a *child* of the API, systemd
        kills the whole service cgroup on restart — including this child — so the
        update dies half-applied. Running it in a new session (setsid) detaches it
        from that cgroup so it survives the restart and runs to completion.

        Output can't be captured (we return immediately), so it is redirected to
        {LOG_DIR}/update.log for inspection.
        """
        update_log = LOG_DIR / "update.log"
        update_log.parent.mkdir(parents=True, exist_ok=True)
        # Truncate (mode "w") so each run starts with a clean log — the UI tails
        # this file for live progress, and a start sentinel on the first line
        # lets the client detect a fresh run and distinguish it from stale output
        # (e.g. a prior run's "a password is required" refusal).
        log_file = open(update_log, "w")
        log_file.write(f"{_UPDATE_LOG_START} {' '.join(flags)}\n")
        log_file.flush()
        # _privileged_command resolves `bash` to its absolute path so the
        # `sudo -n` invocation matches the absolute-path setup.sh grant.
        cmd = _privileged_command("bash", str(_PROJECT_ROOT / "setup.sh"), *flags)
        logger.info(f"Launching detached: {' '.join(cmd)} (output -> {update_log})")
        subprocess.Popen(
            cmd,
            cwd=str(_PROJECT_ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    # ------------------------------------------------------------------ #
    # Process restarts (exposed via /system/restart-{api,display,website})
    # ------------------------------------------------------------------ #
    def restart_api(self) -> None:
        """Restart the API process.

        Prod: restart the systemd unit, DETACHED so the restart (which kills this
        cgroup) can't kill the command issuing it. Dev: uvicorn runs with --reload
        in a screen session, so there is nothing to restart here.
        """
        if is_dev_mode():
            logger.info("restart_api: dev mode (uvicorn --reload) — no action needed")
            return
        logger.info("Restarting nuggies-api.service (detached)")
        subprocess.Popen(
            _privileged_command("systemctl", "restart", "nuggies-api.service"),
            start_new_session=True,
        )

    def restart_display(self) -> str:
        """Stop and restart the active display process. Returns the mode started."""
        mode = _read_settings().get("active_display", "mta")
        logger.info(f"Restarting display (mode={mode})")
        _stop_display()
        _start_display(mode)
        return mode

    def restart_website(self) -> str:
        """Restart the website.

        Prod: the API serves website/dist, so a 'restart' means rebuilding the
        bundle (detached, via setup.sh's build path is overkill — build directly).
        Dev: the webpack dev server runs in the 'nuggies-web' screen session;
        restart that session. Returns which action was taken.
        """
        if is_dev_mode():
            logger.info("Restarting dev website (nuggies-web screen session)")
            # Kill any existing session, then start a fresh one detached.
            subprocess.run(
                ["screen", "-S", "nuggies-web", "-X", "quit"],
                capture_output=True,
            )
            subprocess.Popen(
                [
                    "screen",
                    "-dmS",
                    "nuggies-web",
                    "bash",
                    "-c",
                    f"cd {_PROJECT_ROOT / 'website'} && npm start",
                ],
                start_new_session=True,
            )
            return "dev-server-restarted"

        logger.info("Rebuilding website bundle (prod)")
        website_dir = _PROJECT_ROOT / "website"
        build_log = LOG_DIR / "update.log"
        build_log.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(build_log, "a")
        subprocess.Popen(
            ["npm", "run", "build"],
            cwd=str(website_dir),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        return "bundle-rebuilding"

    def factory_reset(self) -> None:
        """Reset settings to defaults, pull latest code, reapply setup, restart service."""
        logger.info("Factory reset: restoring default settings + full re-setup")
        self.stop_display()

        # Fix settings file permissions in case root owns it from a previous run
        settings_path = _PROJECT_ROOT / "api" / "settings.json"
        if settings_path.exists():
            chmod_cmd = _privileged_command("chmod", "666", str(settings_path))
            result = subprocess.run(chmod_cmd, capture_output=True)
            if result.returncode != 0:
                err = result.stderr.decode(errors="replace").strip()
                logger.error(
                    f"Failed to fix settings permissions ({' '.join(chmod_cmd)}): {err}"
                )

        self.reset_settings()

        # Run setup.sh --update --reboot DETACHED to pull latest code, reapply
        # permissions, and ALWAYS reboot (a factory reset must come up fresh
        # regardless of dev/prod). It restarts the API service, which would kill
        # this process if setup.sh were a child — so detach it.
        logger.info("Launching setup.sh --update --reboot (detached) for full re-setup...")
        self._run_setup_detached("--update", "--reboot")

    def factory_reset_wifi(self) -> None:
        """Reset settings, pull latest code, reapply setup, mark WiFi for wipe, then restart captive-portal."""
        logger.info(
            "Full factory reset: settings + re-setup + WiFi wipe + service restart"
        )
        self.stop_display()

        # Fix settings file permissions in case root owns it from a previous run
        settings_path = _PROJECT_ROOT / "api" / "settings.json"
        if settings_path.exists():
            chmod_cmd = _privileged_command("chmod", "666", str(settings_path))
            result = subprocess.run(chmod_cmd, capture_output=True)
            if result.returncode != 0:
                err = result.stderr.decode(errors="replace").strip()
                logger.error(
                    f"Failed to fix settings permissions ({' '.join(chmod_cmd)}): {err}"
                )

        self.reset_settings()

        # Write the WiFi-wipe markers BEFORE launching setup.sh. setup.sh --update
        # ends by rebooting (prod); on reboot the captive-portal boot service reads
        # these markers and comes up in setup mode. Writing them first guarantees
        # they're in place when the reboot happens.
        try:
            if WIFI_FLAG.exists():
                WIFI_FLAG.unlink()
            _FACTORY_WIFI_RESET.touch()
            # Additive: also force the portal so a reset device reaches the setup page
            # even if a stale association survives the wipe. This does not replace the
            # `.factory_wifi_reset` write above (which retains its existing semantics).
            FORCE_PORTAL.touch()
            logger.info("Wrote .factory_wifi_reset and .force_portal markers")
        except Exception as e:
            logger.error(f"Failed to write reset marker: {e}")
            raise

        # Run setup.sh --update --reboot DETACHED (pull code, reapply permissions,
        # then ALWAYS reboot). The forced reboot brings the device up into the
        # setup portal via the markers written above — and happens on dev too,
        # where a plain --update would not reboot and the reset would stall.
        # Detached so the service restart/reboot can't kill it.
        logger.info("Launching setup.sh --update --reboot (detached) for full re-setup...")
        self._run_setup_detached("--update", "--reboot")

    def force_wifi_portal(self) -> None:
        """Force the captive-setup portal to come up on the next boot of the service.

        Writes the FORCE_PORTAL marker (the boot service already honours it as a
        first-class ``unconfigured``/``forced`` verdict), clears the ``.wifi_configured``
        cache through the shared resolver, then restarts ``nuggies-wifi-setup.service``
        DETACHED so the HTTP response flushes before the restart drops the WiFi
        association. The restart command carries the full ``.service`` suffix so it
        matches the sudoers NOPASSWD grant exactly — the suffix-less form prompts for a
        password and the restart silently never happens.
        """
        logger.info("Forcing WiFi setup portal: writing .force_portal, clearing flag")
        try:
            FORCE_PORTAL.touch()
            _clear_configured()
            logger.info("Wrote .force_portal marker and cleared .wifi_configured cache")
        except Exception as e:
            logger.error(f"Failed to write force-portal marker: {e}")
            raise
        # Detach so the HTTP response flushes before the service restart hands the radio
        # to the setup AP and disrupts the network (mirrors factory_reset_wifi).
        subprocess.Popen(
            _privileged_command("systemctl", "restart", "nuggies-wifi-setup.service"),
            start_new_session=True,
        )

    def _pull_latest_code(self) -> bool:
        """Fast-forward the working tree to the tracked remote branch.

        A plain `git pull` fails on an appliance whose tree has drifted: setup.sh
        rewrites tracked file modes (chmod/chown) and a prior root-level pull can
        leave a dirty or diverged tree, either of which aborts `pull` with a
        non-zero exit. We instead fetch, resolve the upstream ref, and hard-reset
        onto it so the update lands regardless of local mode/content drift.

        Returns True on success, False otherwise (caller decides whether to abort).
        """
        fetch = subprocess.run(
            ["git", "-C", str(_PROJECT_ROOT), "fetch", "origin", "--prune"],
            capture_output=True,
            text=True,
        )
        if fetch.returncode != 0:
            logger.error(
                f"git fetch failed (rc={fetch.returncode}): {fetch.stderr.strip()}"
            )
            return False

        # Resolve the upstream tracking ref (e.g. origin/main); fall back to
        # origin/<current-branch> if no upstream is configured.
        upstream = subprocess.run(
            [
                "git",
                "-C",
                str(_PROJECT_ROOT),
                "rev-parse",
                "--abbrev-ref",
                "--symbolic-full-name",
                "@{u}",
            ],
            capture_output=True,
            text=True,
        )
        if upstream.returncode == 0 and upstream.stdout.strip():
            target = upstream.stdout.strip()
        else:
            branch = subprocess.run(
                ["git", "-C", str(_PROJECT_ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
            )
            current = branch.stdout.strip() or "main"
            target = f"origin/{current}"
            logger.warning(f"No upstream configured; falling back to {target}")

        reset = subprocess.run(
            ["git", "-C", str(_PROJECT_ROOT), "reset", "--hard", target],
            capture_output=True,
            text=True,
        )
        if reset.returncode != 0:
            logger.error(
                f"git reset --hard {target} failed (rc={reset.returncode}): {reset.stderr.strip()}"
            )
            return False

        logger.info(f"Updated working tree to {target}: {reset.stdout.strip()}")
        return True

    async def update_app(self, run_setup: bool = True, mode: str | None = None) -> None:
        """Pull latest code, optionally re-run setup, then reboot.

        *mode* is the setup.sh flag ("--dev"/"--prod"). When the caller resolves it
        (the /update-app endpoint does, so the reported mode matches the executed
        one), it is passed through here; otherwise it is resolved from dev_config.
        """
        await asyncio.sleep(1)  # let HTTP response flush before blocking

        logger.info("Updating to latest code...")
        if not self._pull_latest_code():
            logger.error("Aborting update: could not update code. NOT rebooting.")
            return

        if run_setup:
            # Always use the lightweight updater. The full --dev/--prod installer
            # re-runs apt upgrades / node install / display verification and
            # self-reboots — too heavy and failure-prone for an in-field update.
            # Run it DETACHED: setup.sh --update restarts the API service, which
            # would kill this process (and setup.sh with it) if run as a child.
            # Because it's detached, we hand reboot/restart duty to setup.sh and
            # do NOT reboot here (the old reboot would race the detached update).
            flag = mode or "--update"
            logger.info(f"Launching setup.sh {flag} (detached) to apply update")
            self._run_setup_detached(flag)
            return

        logger.info("Rebooting Pi after update (no setup requested)...")
        self.reboot()
