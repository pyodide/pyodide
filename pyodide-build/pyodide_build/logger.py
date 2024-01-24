import logging
import os
from collections.abc import Generator
from contextlib import contextmanager

from rich.console import Console
from rich.highlighter import NullHighlighter
from rich.logging import RichHandler
from rich.theme import Theme

IN_CI = "CI" in os.environ
IN_PYTEST = "IN_PYTEST" in os.environ

COLOR_THEME = Theme(
    {
        "debug": "",
        "info": "",
        "warning": "bold yellow",
        "error": "bold red",
        "critical": "bold red",
    }
)

LEVEL_STDOUT = logging.INFO - 5
LEVEL_STDERR = logging.INFO + 5


# Note: it seems like rich's auto terminal detection mechanism doesn't work well for CircleCI.
#       so we manually disable it when running in CI.
class CIAwareConsole(Console):
    @property
    def is_terminal(self) -> bool:
        """Check if the console is writing to a terminal."""
        return not IN_CI and not IN_PYTEST and super().is_terminal


class StdoutFilter(logging.Filter):
    def filter(self, record):
        return record.levelno in (LEVEL_STDOUT, logging.DEBUG, logging.INFO)


class StderrFilter(logging.Filter):
    def filter(self, record):
        return record.levelno in (
            LEVEL_STDERR,
            logging.WARNING,
            logging.ERROR,
            logging.CRITICAL,
        )


class _Logger(logging.Logger):
    def success(self, msg, *args, **kwargs):
        self.info("[bold green]%s[/bold green]", msg, *args, **kwargs)

    def stdout(self, msg, *args, **kwargs):
        self.log(LEVEL_STDOUT, msg, *args, **kwargs)

    def stderr(self, msg, *args, **kwargs):
        self.log(LEVEL_STDERR, msg, *args, **kwargs)


class RichFormatter(logging.Formatter):
    """Colorize log messages based on log level."""

    def format(self, records: logging.LogRecord) -> str:
        levelname = records.levelname.lower()
        records.msg = f"[{levelname}]{records.msg}[/{levelname}]"

        formatted = super().format(records)
        return formatted


console_stdout = CIAwareConsole(theme=COLOR_THEME)
console_stderr = CIAwareConsole(stderr=True, theme=COLOR_THEME)


def _get_logger(log_level: int) -> _Logger:
    logger = _Logger(__name__)
    logger.setLevel(log_level)

    rich_handler_stdout = RichHandler(
        console=console_stdout,
        highlighter=NullHighlighter(),
        show_time=False,
        show_level=False,
        show_path=False,
        markup=True,
    )
    rich_handler_stdout.setFormatter(RichFormatter("%(message)s"))
    rich_handler_stderr = RichHandler(
        console=console_stderr,
        highlighter=NullHighlighter(),
        show_time=False,
        show_level=False,
        show_path=False,
        markup=True,
    )
    rich_handler_stderr.setFormatter(RichFormatter("%(message)s"))

    rich_handler_stdout.addFilter(StdoutFilter())
    rich_handler_stderr.addFilter(StderrFilter())

    logger.addHandler(rich_handler_stdout)
    logger.addHandler(rich_handler_stderr)

    return logger


logger = _get_logger(logging.INFO)


@contextmanager
def set_log_level(
    _logger: logging.Logger, log_level: int | bool
) -> Generator[None, None, None]:
    """Set the log level.

    Parameters
    ----------
    logger
        The logger to set the log level for.

    log_level
        If True, set the log level to DEBUG (verbose mode).
        If given an integer, set the log level to that value.
    """

    original_log_level = logger.level

    if isinstance(log_level, bool):
        log_level = logging.DEBUG if log_level else original_log_level

    _logger.setLevel(log_level)

    yield

    _logger.setLevel(original_log_level)


if __name__ == "__main__":
    # For testing the colors
    logger.debug("debug")
    logger.info("info")
    logger.stdout("stdout")
    logger.warning("warning")
    logger.error("error")
    logger.success("success")
    logger.stderr("stderr")
