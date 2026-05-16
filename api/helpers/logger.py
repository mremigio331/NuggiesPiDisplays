import logging
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("/var/log/nuggies")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Holds the request ID for the current API request; injected into every log record.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.req_id = request_id_var.get()
        return True


def setup_logging() -> None:
    req_filter = _RequestIdFilter()

    app_fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(req_id)s] %(name)s: %(message)s"
    )
    svc_fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    # application.log — all API logs, includes req_id in every line
    app_fh = RotatingFileHandler(
        LOG_DIR / "application.log", maxBytes=5_000_000, backupCount=3
    )
    app_fh.setFormatter(app_fmt)
    app_fh.addFilter(req_filter)

    app_ch = logging.StreamHandler()
    app_ch.setFormatter(app_fmt)
    app_ch.addFilter(req_filter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(app_fh)
    root.addHandler(app_ch)

    # service.log — HTTP access log only; isolated from application.log
    svc_fh = RotatingFileHandler(
        LOG_DIR / "service.log", maxBytes=5_000_000, backupCount=3
    )
    svc_fh.setFormatter(svc_fmt)

    svc_logger = logging.getLogger("middleware.service_log")
    svc_logger.addHandler(svc_fh)
    svc_logger.propagate = False


def set_log_level(level: str) -> None:
    """Update the root logger level at runtime after settings are loaded."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric)
