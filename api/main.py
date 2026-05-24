from helpers.logger import setup_logging, set_log_level

setup_logging()

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from helpers.config import read_settings
from helpers.process import start_display
from helpers.buttons import poll_buttons
from helpers.wifi_state import WIFI_FLAG
from middleware.service_log import ServiceLogMiddleware
from endpoints.docs import router as docs_router
from endpoints.home import router as home_router
from endpoints.spa import router as spa_router
from endpoints.system import router as system_router
from endpoints.stonks import router as stonks_router
from endpoints.mta import router as mta_router
from endpoints.clock import router as clock_router
from endpoints.weather import router as weather_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = read_settings()

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
            try:
                start_display(mode)
                logger.info(f"Auto-started {mode} display on launch")
            except Exception as e:
                logger.warning(f"Auto-start display failed: {e}")
    else:
        logger.debug("Auto-start disabled")

    asyncio.create_task(poll_buttons())
    yield


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
app.include_router(weather_router, prefix="/api")

# SPA catch-all — must be last. Serves the built React app for any path not matched above.
app.include_router(spa_router)
