from rich.console import Console
from rich.spinner import Spinner
from rich.theme import Theme

color_theme = Theme(
    {
        "info": "cyan1",
        "warning": "yellow1",
        "error": "red1",
        "success": "green1",
    }
)


class PyodideConsole(Console):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, theme=color_theme)

    def info(self, *args, **kwargs):
        self.print(*args, **kwargs, style="info")

    def warning(self, *args, **kwargs):
        self.print(*args, **kwargs, style="warning")

    def error(self, *args, **kwargs):
        self.print(*args, **kwargs, style="error")

    def success(self, *args, **kwargs):
        self.print(*args, **kwargs, style="success")


console_stdout = PyodideConsole()
console_stderr = PyodideConsole(stderr=True)


def spinner() -> Spinner | None:
    import os

    # Spinner pollutes the output in CI
    if "CI" in os.environ:
        return None
    else:
        return Spinner("dots", style="red")


if __name__ == "__main__":
    # For testing the colors
    console_stdout.print("print")
    console_stdout.info("info")
    console_stdout.warning("warning")
    console_stdout.error("error")
    console_stdout.success("success")
