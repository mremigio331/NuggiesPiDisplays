import asyncio
import logging
import os
import subprocess

from helpers.config import reset_settings as _reset_settings
from helpers.dev_config import is_dev_mode
from helpers.process import _PROJECT_ROOT, stop_display as _stop_display
from helpers.wifi_state import FORCE_PORTAL, WIFI_FLAG

# Importing `helpers.wifi_state` above inserts the project root onto sys.path, so the
# shared resolver package is importable from the api-rooted working directory. Clear the
# `.wifi_configured` cache through the resolver so the marker semantics stay owned by the
# single source of truth (wifi_setup/wifi_state.py) rather than duplicated here.
from wifi_setup.wifi_state import clear_configured as _clear_configured

logger = logging.getLogger(__name__)

_FACTORY_WIFI_RESET = _PROJECT_ROOT / ".factory_wifi_reset"


def _privileged_command(*args: str) -> list[str]:
    # If already root (e.g., service user), run command directly.
    if os.geteuid() == 0:
        return list(args)
    # -n prevents hanging on password prompts in HTTP request handlers.
    return ["sudo", "-n", *args]


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

        # Run setup.sh --update to pull latest code, reapply permissions, restart service
        logger.info("Running setup.sh --update for full re-setup...")
        result = subprocess.run(
            _privileged_command("bash", str(_PROJECT_ROOT / "setup.sh"), "--update"),
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(f"setup.sh --update failed: {result.stderr}")
        else:
            logger.info("Factory reset complete — setup reapplied")

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

        # Run setup.sh --update to pull latest code, reapply permissions
        logger.info("Running setup.sh --update for full re-setup...")
        result = subprocess.run(
            _privileged_command("bash", str(_PROJECT_ROOT / "setup.sh"), "--update"),
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(f"setup.sh --update failed: {result.stderr}")
        else:
            logger.info("Setup reapplied successfully")

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
        # Detach so the HTTP response flushes before the service restart
        # wipes the WiFi connection and disrupts the network.
        subprocess.Popen(
            _privileged_command("systemctl", "restart", "nuggies-wifi-setup.service"),
            start_new_session=True,
        )

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

    async def update_app(self, run_setup: bool = True) -> None:
        """Pull latest code, optionally re-run setup, then reboot."""
        await asyncio.sleep(1)  # let HTTP response flush before blocking

        logger.info("Running git pull...")
        pull = subprocess.run(
            ["git", "-C", str(_PROJECT_ROOT), "pull"],
            capture_output=True,
            text=True,
        )
        logger.info(f"git pull stdout: {pull.stdout.strip()}")
        if pull.returncode != 0:
            logger.warning(f"git pull stderr: {pull.stderr.strip()}")

        if run_setup:
            mode = "--dev" if is_dev_mode() else "--prod"
            logger.info(f"Running setup.sh {mode}...")
            subprocess.run(
                _privileged_command("bash", str(_PROJECT_ROOT / "setup.sh"), mode),
                cwd=str(_PROJECT_ROOT),
            )

        logger.info("Rebooting Pi after update...")
        self.reboot()
