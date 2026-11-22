from helpers.logger import setup_logging, set_log_level

setup_logging()

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from helpers.config import read_settings
from helpers.process import start_display, is_running
from helpers.buttons import poll_buttons
from helpers.power_led import power_led, run_power_led
from helpers.wifi_state import WIFI_FLAG
from helpers.update_check import run_background_checker
from helpers.schedule import run_scheduler
from helpers.cycle import run_cycler
from helpers.timers import run_timer_watcher
from helpers.health import run_health_logger
from helpers.system import clear_update_lock
from middleware.service_log import ServiceLogMiddleware
from endpoints.docs import router as docs_router
from endpoints.home import router as home_router
from endpoints.spa import router as spa_router
from endpoints.system import router as system_router
from endpoints.stonks import router as stonks_router
from endpoints.mta import router as mta_router
from endpoints.clock import router as clock_router
from endpoints.flight import router as flight_router
from endpoints.text import router as text_router
from endpoints.timers import router as timers_router
from endpoints.sports import router as sports_router
from endpoints.weather import router as weather_router
from endpoints.wifi import router as wifi_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = read_settings()

    # Clear any update lock left over from a crash mid-update. A clean finish or
    # a clean failure removes the lock in setup.sh's EXIT trap; only a hard crash
    # (power loss, kill) leaves it behind — and that is always followed by this
    # boot. So clearing it here guarantees a wedged device can always update
    # again. Nothing is in progress on a fresh boot, so this frees nothing live.
    clear_update_lock()

    log_level = settings.get("log_level", "INFO")
    set_log_level(log_level)
    logger.info(f"Log level: {log_level}")

    if not WIFI_FLAG.exists():
        logger.info(
            "WiFi not configured — skipping auto-start display (setup display is running)"
        )
    elif settings.get("auto_start_display", True):
        mode = settings.get("active_display")
        logger.debug(f"Auto-start enabled, active_display={mode}")
        if mode:
            # Skip auto-start if the display is already running (e.g. uvicorn --reload)
            if is_running():
                logger.debug("Display already running, skipping auto-start")
            else:
                try:
                    start_display(mode)
                    logger.info(f"Auto-started {mode} display on launch")
                except Exception as e:
                    logger.warning(f"Auto-start display failed: {e}")
    else:
        logger.debug("Auto-start disabled")

    asyncio.create_task(poll_buttons())
    asyncio.create_task(run_background_checker())
    asyncio.create_task(run_scheduler())
    asyncio.create_task(run_cycler())
    asyncio.create_task(run_timer_watcher())
    # Logs CPU temp, CPU use and memory every 10 minutes (System > Health).
    asyncio.create_task(run_health_logger())
    # Power button LED tracks device status: green display on, blue display on
    # with an update ready, red display off, blue pulse while updating, green
    # pulse in WiFi setup.
    asyncio.create_task(run_power_led())
    yield
    # Service stopping (systemctl stop/restart, or the reboot/shutdown that stops
    # every service) — show red. Latched so the status loop can't repaint it.
    power_led.latch("red")


# Disable FastAPI's internal docs routes — they're registered as low-priority Route objects
# that lose to the SPA catch-all below. We re-register them as explicit APIRoutes instead.
app = FastAPI(
    title="Nuggies Pi Displays",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.add_middleware(ServiceLogMiddleware)


# Docs and API routes — registered before the SPA catch-all so they win on priority.
app.include_router(docs_router)
app.include_router(home_router)
app.include_router(system_router, prefix="/api")
app.include_router(stonks_router, prefix="/api")
app.include_router(mta_router, prefix="/api")
app.include_router(clock_router, prefix="/api")
app.include_router(flight_router, prefix="/api")
app.include_router(text_router, prefix="/api")
app.include_router(timers_router, prefix="/api")
app.include_router(sports_router, prefix="/api")
app.include_router(weather_router, prefix="/api")
app.include_router(wifi_router, prefix="/api")

# SPA catch-all — must be last. Serves the built React app for any path not matched above.
app.include_router(spa_router)
