import logging
import os

from rich.console import Console
from rich.highlighter import NullHighlighter
from rich.logging import RichHandler
from rich.theme import Theme

IN_CI = "CI" in os.environ

COLOR_THEME = Theme(
    {
        "debug": "",
        "info": "",
        "warning": "bold yellow",
        "error": "bold red",
        "critical": "red",
    }
)


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


class _Logger(logging.Logger):
    def success(self, msg, *args, **kwargs):
        self.info("[bold green]%s[/bold green]", msg, *args, **kwargs)


class RichFormatter(logging.Formatter):
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

    # Print only info and below to stdout, and above to stderr
    rich_handler_stdout.addFilter(InfoFilter())
    rich_handler_stderr.addFilter(ErrorFilter())

    logger.addHandler(rich_handler_stdout)
    logger.addHandler(rich_handler_stderr)

    return logger


logger = _get_logger(logging.DEBUG)

if __name__ == "__main__":
    # For testing the colors
    logger.debug("debug")
    logger.info("info")
    logger.warning("warning")
    logger.error("error")
