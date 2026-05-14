from helpers.logger import setup_logging

setup_logging()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from middleware.service_log import ServiceLogMiddleware
from endpoints.home import router as home_router
from endpoints.system import router as system_router
from endpoints.stonks import router as stonks_router
from endpoints.mta import router as mta_router
from endpoints.clock import router as clock_router
from endpoints.weather import router as weather_router

app = FastAPI(title="Nuggies Pi Displays", version="1.0.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.add_middleware(ServiceLogMiddleware)

app.include_router(home_router)
app.include_router(system_router)
app.include_router(stonks_router)
app.include_router(mta_router)
app.include_router(clock_router)
app.include_router(weather_router)
