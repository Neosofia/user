from logenvelope.events import log_event
from logenvelope.formatter import JSONFormatter
from logenvelope.setup import setup_logging as _setup_logging


def setup_logging(name: str, level: str) -> None:
    _setup_logging(name, level)


__all__ = ["JSONFormatter", "log_event", "setup_logging"]
