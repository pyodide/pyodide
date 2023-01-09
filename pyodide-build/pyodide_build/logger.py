import logging

from rich.console import Console
from rich.logging import RichHandler
from rich.spinner import Spinner


class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno in (logging.DEBUG, logging.INFO)


class ErrorFilter(logging.Filter):
    def filter(self, record):
        return record.levelno in (logging.WARNING, logging.ERROR)


class RichFormatter(logging.Formatter):
    def format(self, records: logging.LogRecord) -> str:
        # TODO: color the output
        formatted = super().format(records)
        return formatted


def _get_logger() -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    rich_handler_stdout = RichHandler(
        console=Console(),
        show_time=False,
        show_level=False,
        show_path=False,
        markup=True,
    )
    rich_handler_stdout.setFormatter(RichFormatter("%(message)s"))
    rich_handler_stderr = RichHandler(
        console=Console(stderr=True),
        show_time=False,
        show_level=False,
        show_path=False,
        markup=True,
    )
    rich_handler_stderr.setFormatter(RichFormatter("%(message)s"))

    # Print only info and below to stdout, and above to stderr
    rich_handler_stdout.addFilter(InfoFilter())
    rich_handler_stderr.addFilter(ErrorFilter())

    logger.addHandler(rich_handler_stdout)
    logger.addHandler(rich_handler_stderr)

    return logger


logger = _get_logger()


def spinner() -> Spinner | None:
    import os

    # Spinner pollutes the output in CI
    if "CI" in os.environ:
        return None
    else:
        return Spinner("dots", style="red")


if __name__ == "__main__":
    # For testing the colors
    logger.debug("debug")
    logger.info("info")
    logger.warning("warning")
    logger.error("error")
