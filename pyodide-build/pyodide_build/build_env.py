import functools
import os
import subprocess
import sys
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path

if sys.version_info < (3, 11, 0):
    import tomli as tomllib
else:
    import tomllib

from .logger import logger

BUILD_VARS: set[str] = {
    "PATH",
    "PYTHONPATH",
    "PYODIDE_ROOT",
    "PYTHONINCLUDE",
    "NUMPY_LIB",
    "PYODIDE_PACKAGE_ABI",
    "HOME",
    "HOSTINSTALLDIR",
    "TARGETINSTALLDIR",
    "SYSCONFIG_NAME",
    "HOSTSITEPACKAGES",
    "PYVERSION",
    "PYMAJOR",
    "PYMINOR",
    "PYMICRO",
    "CPYTHONBUILD",
    "CPYTHONLIB",
    "SIDE_MODULE_CFLAGS",
    "SIDE_MODULE_CXXFLAGS",
    "SIDE_MODULE_LDFLAGS",
    "STDLIB_MODULE_CFLAGS",
    "UNISOLATED_PACKAGES",
    "WASM_LIBRARY_DIR",
    "WASM_PKG_CONFIG_PATH",
    "CARGO_BUILD_TARGET",
    "CARGO_TARGET_WASM32_UNKNOWN_EMSCRIPTEN_LINKER",
    "RUSTFLAGS",
    "PYO3_CROSS_LIB_DIR",
    "PYO3_CROSS_INCLUDE_DIR",
    "PYODIDE_EMSCRIPTEN_VERSION",
    "PLATFORM_TRIPLET",
    "SYSCONFIGDATA_DIR",
    "RUST_TOOLCHAIN",
}


def init_environment(*, quiet: bool = False) -> None:
    """
    Initialize Pyodide build environment.
    This function needs to be called before any other Pyodide build functions.
    """
    if os.environ.get("__LOADED_PYODIDE_ENV"):
        return

    os.environ["__LOADED_PYODIDE_ENV"] = "1"

    _set_pyodide_root(quiet=quiet)


@functools.cache
def get_pyodide_root() -> Path:
    init_environment()
    return Path(os.environ["PYODIDE_ROOT"])


def in_xbuildenv() -> bool:
    pyodide_root = get_pyodide_root()
    return pyodide_root.name == "pyodide-root"


def search_pyodide_root(curdir: str | Path, *, max_depth: int = 5) -> Path:
    """
    Recursively search for the root of the Pyodide repository,
    by looking for the pyproject.toml file in the parent directories
    which contains [tool.pyodide] section.
    """

    # We want to include "curdir" in parent_dirs, so add a garbage suffix
    parent_dirs = (Path(curdir) / "garbage").parents[:max_depth]

    for base in parent_dirs:
        pyproject_file = base / "pyproject.toml"

        if not pyproject_file.is_file():
            continue

        try:
            with pyproject_file.open("rb") as f:
                configs = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Could not parse {pyproject_file}.") from e

        if "tool" in configs and "pyodide" in configs["tool"]:
            return base

    raise FileNotFoundError(
        "Could not find Pyodide root directory. If you are not in the Pyodide directory, set `PYODIDE_ROOT=<pyodide-root-directory>`."
    )


@functools.cache
def get_build_environment_vars() -> dict[str, str]:
    """
    Get common environment variables for the in-tree and out-of-tree build.
    """
    env = _get_make_environment_vars().copy()
    env["PYODIDE"] = "1"

    if "PYODIDE_JOBS" in os.environ:
        env["PYODIDE_JOBS"] = os.environ["PYODIDE_JOBS"]

    env["PKG_CONFIG_PATH"] = env["WASM_PKG_CONFIG_PATH"]
    if "PKG_CONFIG_PATH" in os.environ:
        env["PKG_CONFIG_PATH"] += f":{os.environ['PKG_CONFIG_PATH']}"

    tools_dir = Path(__file__).parent / "tools"

    env["CMAKE_TOOLCHAIN_FILE"] = str(
        tools_dir / "cmake/Modules/Platform/Emscripten.cmake"
    )
    env["PYO3_CONFIG_FILE"] = str(tools_dir / "pyo3_config.ini")

    hostsitepackages = env["HOSTSITEPACKAGES"]
    pythonpath = [
        hostsitepackages,
    ]
    env["PYTHONPATH"] = ":".join(pythonpath)
    return env


def get_build_flag(name: str) -> str:
    """
    Get a value of a build flag.
    """
    build_vars = get_build_environment_vars()
    if name not in build_vars:
        raise ValueError(f"Unknown build flag: {name}")

    return build_vars[name]


def _set_pyodide_root(*, quiet: bool = False) -> None:
    """
    Initialize Pyodide build environment, namely set PYODIDE_ROOT environment variable.

    This function works both in-tree and out-of-tree builds:
    - In-tree builds: Searches for the root of the Pyodide repository in parent directories
    - Out-of-tree builds: Downloads and installs the Pyodide build environment into the current directory

    Parameters
    ----------
    quiet
        If True, do not print any messages
    """

    from . import install_xbuildenv  # avoid circular import

    # If we are building docs, we don't need to know the PYODIDE_ROOT
    if "sphinx" in sys.modules:
        os.environ["PYODIDE_ROOT"] = ""
        return

    # 1) If PYODIDE_ROOT is already set, do nothing
    if "PYODIDE_ROOT" in os.environ:
        return

    # 2) If we are doing an in-tree build,
    #    set PYODIDE_ROOT to the root of the Pyodide repository
    try:
        os.environ["PYODIDE_ROOT"] = str(search_pyodide_root(Path.cwd()))
        return
    except FileNotFoundError:
        pass

    # 3) If we are doing an out-of-tree build,
    #    download and install the Pyodide build environment
    xbuildenv_path = Path(".pyodide-xbuildenv").resolve()

    if xbuildenv_path.exists():
        os.environ["PYODIDE_ROOT"] = str(xbuildenv_path / "xbuildenv" / "pyodide-root")
        return

    with ExitStack() as stack:
        if quiet:
            # Prevent writes to stdout
            stack.enter_context(redirect_stdout(StringIO()))

        # install_xbuildenv will set PYODIDE_ROOT env variable, so we don't need to do it here
        # TODO: return the path to the xbuildenv instead of setting the env variable inside install_xbuildenv
        install_xbuildenv.install(xbuildenv_path, download=True)


@functools.cache
def _get_make_environment_vars() -> dict[str, str]:
    """
    Load environment variables from Makefile.envs

    This is not a public API, use get_build_environment_vars instead.
    """

    from .common import exit_with_stdio  # avoid circular import

    PYODIDE_ROOT = get_pyodide_root()
    environment = {}
    result = subprocess.run(
        ["make", "-f", str(PYODIDE_ROOT / "Makefile.envs"), ".output_vars"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("ERROR: Failed to load environment variables from Makefile.envs")
        exit_with_stdio(result)

    for line in result.stdout.splitlines():
        equalPos = line.find("=")
        if equalPos != -1:
            varname = line[0:equalPos]

            if varname not in BUILD_VARS:
                continue

            value = line[equalPos + 1 :]
            value = value.strip("'").strip()
            environment[varname] = value
    return environment
