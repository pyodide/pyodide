import logging
import os

from rich.console import Console
from rich.logging import RichHandler

IN_CI = "CI" in os.environ


# Note: it seems like rich's auto terminal detection mechanism doesn't work well for CircleCI.
#       so we manually disable it when running in CI.
class CIAwareConsole(Console):
    @property
    def is_terminal(self) -> bool:
        """Check if the console is writing to a terminal."""
        return not IN_CI and super().is_terminal


class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno in (logging.DEBUG, logging.INFO)


class ErrorFilter(logging.Filter):
    def filter(self, record):
        return record.levelno in (logging.WARNING, logging.ERROR, logging.CRITICAL)


class RichFormatter(logging.Formatter):
    def format(self, records: logging.LogRecord) -> str:
        # TODO: color the output
        formatted = super().format(records)
        return formatted


console_stdout = CIAwareConsole()
console_stderr = CIAwareConsole(stderr=True)


def _get_logger() -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    rich_handler_stdout = RichHandler(
        console=console_stdout,
        show_time=False,
        show_level=False,
        show_path=False,
        markup=True,
    )
    rich_handler_stdout.setFormatter(RichFormatter("%(message)s"))
    rich_handler_stderr = RichHandler(
        console=console_stderr,
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

if __name__ == "__main__":
    # For testing the colors
    logger.debug("debug")
    logger.info("info")
    logger.warning("warning")
    logger.error("error")
