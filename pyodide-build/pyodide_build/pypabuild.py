import contextlib
import os
import subprocess
import sys
import traceback
from pathlib import Path

from build.env import IsolatedEnvBuilder  # type: ignore[import]
from packaging.requirements import Requirement

from build import (  # type: ignore[import]
    BuildBackendException,
    BuildException,
    ProjectBuilder,
)

from .common import get_make_flag, get_pyversion

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
    if sys.stdout.isatty():
        return _COLORS
    return _NO_COLORS


_STYLES = _init_colors()


def _error(msg: str, code: int = 1) -> None:  # pragma: no cover
    """
    Print an error message and exit. Will color the output when writing to a TTY.

    :param msg: Error message
    :param code: Error code
    """
    print("{red}ERROR{reset} {}".format(msg, **_STYLES))
    exit(code)


class _ProjectBuilder(ProjectBuilder):
    @staticmethod
    def log(message: str) -> None:
        print("{bold}* {}{reset}".format(message, **_STYLES))


class _IsolatedEnvBuilder(IsolatedEnvBuilder):
    @staticmethod
    def log(message: str) -> None:
        print("{bold}* {}{reset}".format(message, **_STYLES))

    def __exit__(self, *args):
        print("EXITING ISOLATED ENV!", self._path)


UNISOLATED_PACKAGES = ["numpy", "scipy"]


def symlink_unisolated_packages(env):
    pyversion = get_pyversion()
    site_packages_path = f"lib/{pyversion}/site-packages"
    env_site_packages = Path(env._path) / site_packages_path
    host_installdir = Path(get_make_flag("HOSTINSTALLDIR"))
    host_site_packages = host_installdir / site_packages_path
    for name in UNISOLATED_PACKAGES:
        for path in host_site_packages.glob(name + "*"):
            (env_site_packages / path.name).unlink(missing_ok=True)
            (env_site_packages / path.name).symlink_to(path)


def remove_unisolated_requirements(env, requires: set[str]) -> set[str]:
    for reqstr in list(requires):
        req = Requirement(reqstr)
        for avoid_name in UNISOLATED_PACKAGES:
            if avoid_name in req.name:
                requires.remove(reqstr)
    print("\n\nrequires", requires)
    print("\n\n")
    return requires


@contextlib.contextmanager
def replace_env(env):
    old_environ = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_environ)


def _build_in_isolated_env(
    build_env, builder: ProjectBuilder, outdir, distribution: str, config_settings
) -> str:
    with _IsolatedEnvBuilder() as env:
        builder.python_executable = env.executable
        builder.scripts_dir = env.scripts_dir
        # first install the build dependencies
        symlink_unisolated_packages(env)
        env.install(remove_unisolated_requirements(env, builder.build_system_requires))
        env.install(
            remove_unisolated_requirements(
                env, builder.get_requires_for_build(distribution)
            )
        )

        with replace_env(build_env):
            return builder.build(distribution, outdir, config_settings or {})


@contextlib.contextmanager
def _handle_build_error():
    try:
        yield
    except BuildException as e:
        _error(str(e))
    except BuildBackendException as e:
        if isinstance(e.exception, subprocess.CalledProcessError):
            print()
        else:
            if e.exc_info:
                tb_lines = traceback.format_exception(
                    e.exc_info[0],
                    e.exc_info[1],
                    e.exc_info[2],
                    limit=-1,
                )
                tb = "".join(tb_lines)
            else:
                tb = traceback.format_exc(-1)
            print("\n{dim}{}{reset}\n".format(tb.strip("\n"), **_STYLES))
        _error(str(e))
        sys.exit(1)


def build(build_env):
    srcdir = Path.cwd()
    outdir = srcdir / "dist"
    builder = _ProjectBuilder(srcdir)
    distribution = "wheel"
    try:
        with _handle_build_error():
            built = _build_in_isolated_env(
                build_env, builder, outdir, distribution, None
            )
            print("{bold}{green}Successfully built {}{reset}".format(built, **_STYLES))
    except Exception as e:  # pragma: no cover
        tb = traceback.format_exc().strip("\n")
        print("\n{dim}{}{reset}\n".format(tb, **_STYLES))
        _error(str(e))
        sys.exit(1)
