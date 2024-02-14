import json
import os
import subprocess
import sys
import textwrap
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from os import PathLike
from pathlib import Path
from subprocess import CompletedProcess
from types import TracebackType
from typing import IO, Any, TextIO, TypeAlias

StrOrBytesPath: TypeAlias = str | bytes | PathLike[str] | PathLike[bytes]
_CMD: TypeAlias = StrOrBytesPath | Sequence[StrOrBytesPath]
_FILE: TypeAlias = None | int | IO[Any]
_ENV: TypeAlias = Mapping[bytes, StrOrBytesPath] | Mapping[str, StrOrBytesPath]

from .build_env import (
    get_build_environment_vars,
    get_pyodide_root,
)
from .common import exit_with_stdio
from .logger import logger


class BashRunnerWithSharedEnvironment:
    """Run multiple bash scripts with persistent environment.

    Environment is stored to "env" member between runs. This can be updated
    directly to adjust the environment, or read to get variables.
    """

    def __init__(self, env: dict[str, str] | None = None) -> None:
        if env is None:
            env = dict(os.environ)

        self._reader: TextIO | None
        self._fd_write: int | None
        self.env: dict[str, str] = env

    def __enter__(self) -> "BashRunnerWithSharedEnvironment":
        fd_read, self._fd_write = os.pipe()
        self._reader = os.fdopen(fd_read, "r")
        return self

    def run_unchecked(self, cmd: str, **opts: Any) -> subprocess.CompletedProcess[str]:
        assert self._fd_write is not None
        assert self._reader is not None

        write_env_pycode = ";".join(
            [
                "import os",
                "import json",
                f'os.write({self._fd_write}, json.dumps(dict(os.environ)).encode() + b"\\n")',
            ]
        )
        write_env_shell_cmd = f"{sys.executable} -c '{write_env_pycode}'"
        full_cmd = f"{cmd}\n{write_env_shell_cmd}"
        result = subprocess.run(
            ["bash", "-ce", full_cmd],
            check=False,
            pass_fds=[self._fd_write],
            env=self.env,
            encoding="utf8",
            **opts,
        )
        if result.returncode == 0:
            self.env = json.loads(self._reader.readline())
        return result

    def run(
        self,
        cmd: str | None,
        *,
        script_name: str,
        cwd: Path | str | None = None,
        **opts: Any,
    ) -> subprocess.CompletedProcess[str] | None:
        """Run a bash script. Any keyword arguments are passed on to subprocess.run."""
        if not cmd:
            return None
        if cwd is None:
            cwd = Path.cwd()
        cwd = Path(cwd).absolute()
        logger.info(f"Running {script_name} in {str(cwd)}")
        opts["cwd"] = cwd
        result = self.run_unchecked(cmd, **opts)
        if result.returncode != 0:
            logger.error(f"ERROR: {script_name} failed")
            logger.error(textwrap.indent(cmd, "    "))
            exit_with_stdio(result)
        return result

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Free the file descriptors."""

        if self._fd_write:
            os.close(self._fd_write)
            self._fd_write = None
        if self._reader:
            self._reader.close()
            self._reader = None


@contextmanager
def get_bash_runner(
    extra_envs: dict[str, str],
) -> Iterator[BashRunnerWithSharedEnvironment]:
    pyodide_root = get_pyodide_root()
    env = get_build_environment_vars()
    env.update(extra_envs)

    with BashRunnerWithSharedEnvironment(env=env) as b:
        # Working in-tree, add emscripten toolchain into PATH and set ccache
        if Path(pyodide_root, "pyodide_env.sh").exists():
            b.run(
                f"source {pyodide_root}/pyodide_env.sh",
                script_name="source pyodide_env",
                stderr=subprocess.DEVNULL,
            )

        yield b


def run_with_venv_context(
    args: _CMD,
    bufsize: int = -1,
    executable: StrOrBytesPath | None = None,
    stdin: _FILE = None,
    stdout: _FILE = None,
    stderr: _FILE = None,
    preexec_fn: Callable[[], Any] | None = None,
    close_fds: bool = True,
    shell: bool = False,
    cwd: StrOrBytesPath | None = None,
    env: _ENV | None = None,
    universal_newlines: bool | None = None,
    startupinfo: Any = None,
    creationflags: int = 0,
    restore_signals: bool = True,
    start_new_session: bool = False,
    pass_fds: Collection[int] = (),
    *,
    capture_output: bool = False,
    check: bool = False,
    encoding: str,
    errors: str | None = None,
    input: str | None = None,
    text: bool | None = None,
    timeout: float | None = None,
    user: str | int | None = None,
    group: str | int | None = None,
    extra_groups: Iterable[str | int] | None = None,
    umask: int = -1,
    pipesize: int = -1,
    process_group: int | None = None,
) -> CompletedProcess[str]:
    kwargs = {
        "bufsize": bufsize,
        "executable": executable,
        "stdin": stdin,
        "stdout": stdout,
        "stderr": stderr,
        "preexec_fn": preexec_fn,
        "close_fds": close_fds,
        "shell": shell,
        "cwd": cwd,
        "env": env,
        "universal_newlines": universal_newlines,
        "startupinfo": startupinfo,
        "creationflags": creationflags,
        "restore_signals": restore_signals,
        "start_new_session": start_new_session,
        "pass_fds": pass_fds,
        "capture_output": capture_output,
        "check": check,
        "encoding": encoding,
        "errors": errors,
        "input": input,
        "text": text,
        "timeout": timeout,
        "user": user,
        "group": group,
        "extra_groups": extra_groups,
        "umask": umask,
        "pipesize": pipesize,
        "process_group": process_group,
    }
    if sys.prefix == sys.base_prefix:
        # not in venv run normally
        return subprocess.run(args, **kwargs)
    if not env:
        env = os.environ
    env2: dict[str, str] = dict(env)  # type:ignore[arg-type]
    kwargs["env"] = env2
    if env2.get("VIRTUALENV"):
        # activated venv, run normally
        return subprocess.run(args, **kwargs)
    env2["VIRTUALENV"] = sys.prefix
    bin_dir = str(Path(sys.prefix) / "bin")
    orig_path = env2["PATH"]
    env2["PATH"] = f"{bin_dir}:{orig_path}"
    return subprocess.run(args, **kwargs)
