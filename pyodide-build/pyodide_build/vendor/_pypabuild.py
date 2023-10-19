# This file contains private functions taken from pypa/build.

# Copyright © 2019 Filipe Laíns <filipe.lains@gmail.com>

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice (including the next
# paragraph) shall be included in all copies or substantial portions of the
# Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
import contextlib
import os
import subprocess
import sys
import traceback
import warnings
from collections.abc import Iterator
from typing import NoReturn

from build import (
    BuildBackendException,
    BuildException,
    FailedProcessError,
    ProjectBuilder,
)
from build.env import DefaultIsolatedEnv

_COLORS = {
    "red": "\33[91m",
    "green": "\33[92m",
    "yellow": "\33[93m",
    "bold": "\33[1m",
    "dim": "\33[2m",
    "underline": "\33[4m",
    "reset": "\33[0m",
}
_NO_COLORS = {color: "" for color in _COLORS}


def _init_colors() -> dict[str, str]:
    if "NO_COLOR" in os.environ:
        if "FORCE_COLOR" in os.environ:
            warnings.warn(
                "Both NO_COLOR and FORCE_COLOR environment variables are set, disabling color",
                stacklevel=2,
            )
        return _NO_COLORS
    elif "FORCE_COLOR" in os.environ or sys.stdout.isatty():
        return _COLORS
    return _NO_COLORS


_STYLES = _init_colors()


def _cprint(fmt: str = "", msg: str = "") -> None:
    print(fmt.format(msg, **_STYLES), flush=True)


def _error(msg: str, code: int = 1) -> NoReturn:  # pragma: no cover
    """
    Print an error message and exit. Will color the output when writing to a TTY.

    :param msg: Error message
    :param code: Error code
    """
    _cprint("{red}ERROR{reset} {}", msg)
    raise SystemExit(code)


class _ProjectBuilder(ProjectBuilder):
    @staticmethod
    def log(message: str) -> None:
        _cprint("{bold}* {}{reset}", message)


class _DefaultIsolatedEnv(DefaultIsolatedEnv):
    @staticmethod
    def log(message: str) -> None:
        _cprint("{bold}* {}{reset}", message)


@contextlib.contextmanager
def _handle_build_error() -> Iterator[None]:
    try:
        yield
    except (BuildException, FailedProcessError) as e:
        _error(str(e))
    except BuildBackendException as e:
        if isinstance(e.exception, subprocess.CalledProcessError):
            _cprint()
            _error(str(e))

        if e.exc_info:
            tb_lines = traceback.format_exception(
                e.exc_info[0],
                e.exc_info[1],
                e.exc_info[2],
                limit=-1,
            )
            tb = "".join(tb_lines)
        else:
            tb = traceback.format_exc(-1)  # type: ignore[unreachable]
        _cprint("\n{dim}{}{reset}\n", tb.strip("\n"))
        _error(str(e))
