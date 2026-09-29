import contextvars
import logging

_request_id = contextvars.ContextVar("log_request_id", default="-")


class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = _request_id.get()
        return True


def set_log_request_id(value):
    _request_id.set(value or "-")
