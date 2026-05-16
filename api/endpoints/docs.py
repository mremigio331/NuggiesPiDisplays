import logging

from fastapi import APIRouter, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/openapi.json", include_in_schema=False)
async def openapi_schema(request: Request):
    return JSONResponse(request.app.openapi())


@router.get("/docs", include_in_schema=False)
async def swagger_ui():
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Nuggies Pi Displays")
