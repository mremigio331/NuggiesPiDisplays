import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from helpers.logger import request_id_var

logger = logging.getLogger(__name__)


class ServiceLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = uuid.uuid4().hex[:8]
        token = request_id_var.set(req_id)
        start = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            if response is not None:
                response.headers["X-Request-ID"] = req_id
            return response
        finally:
            ms = (time.perf_counter() - start) * 1000
            status = response.status_code if response is not None else "ERR"
            logger.info(
                f"[{req_id}] {request.method} {request.url.path} {status} {ms:.1f}ms"
            )
            request_id_var.reset(token)
