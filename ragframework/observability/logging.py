import contextvars
import logging
import sys

from pythonjsonlogger import json

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        json.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s %(request_id)s"
        )
    )
    handler.addFilter(RequestIDFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
