import asyncio
import logging
import subprocess

from helpers.config import reset_settings as _reset_settings
from helpers.dev_config import is_dev_mode
from helpers.process import _PROJECT_ROOT, stop_display as _stop_display
from helpers.wifi_state import WIFI_FLAG

logger = logging.getLogger(__name__)

_FACTORY_WIFI_RESET = _PROJECT_ROOT / ".factory_wifi_reset"


class SystemManager:
    def reboot(self) -> None:
        logger.info("Rebooting Pi")
        result = subprocess.run(["sudo", "reboot"], capture_output=True)
        if result.returncode != 0:
            err = result.stderr.decode().strip()
            logger.error(f"Reboot failed: {err}")
            raise RuntimeError(f"Reboot failed: {err}")

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
        """Reset settings to defaults. Does not affect WiFi or reboot."""
        logger.info("Factory reset: restoring default settings")
        self.stop_display()
        self.reset_settings()
        logger.info("Factory reset complete")

    def factory_reset_wifi(self) -> None:
        """Reset settings, mark WiFi for wipe on next boot, then reboot."""
        logger.info("Full factory reset: settings + WiFi wipe marker + reboot")
        self.stop_display()
        self.reset_settings()
        try:
            if WIFI_FLAG.exists():
                WIFI_FLAG.unlink()
            _FACTORY_WIFI_RESET.touch()
            logger.info("Wrote .factory_wifi_reset marker")
        except Exception as e:
            logger.error(f"Failed to write reset marker: {e}")
            raise
        self.reboot()

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
                ["sudo", "bash", str(_PROJECT_ROOT / "setup.sh"), mode],
                cwd=str(_PROJECT_ROOT),
            )

        logger.info("Rebooting Pi after update...")
        self.reboot()
