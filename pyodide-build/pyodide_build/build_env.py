# This file contains functions for managing the Pyodide build environment.

import dataclasses
import functools
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from contextlib import nullcontext, redirect_stdout
from io import StringIO
from pathlib import Path

if sys.version_info < (3, 11, 0):  # noqa: UP036
    import tomli as tomllib
else:
    import tomllib

from packaging.tags import Tag, compatible_tags, cpython_tags

from .common import exit_with_stdio
from .logger import logger
from .recipe import load_all_recipes

RUST_BUILD_PRELUDE = """
rustup toolchain install ${RUST_TOOLCHAIN} && rustup default ${RUST_TOOLCHAIN}
rustup target add wasm32-unknown-emscripten --toolchain ${RUST_TOOLCHAIN}
"""


BUILD_VARS: set[str] = {
    "CARGO_BUILD_TARGET",
    "CARGO_TARGET_WASM32_UNKNOWN_EMSCRIPTEN_LINKER",
    "HOME",
    "HOSTINSTALLDIR",
    "HOSTSITEPACKAGES",
    "NUMPY_LIB",
    "PATH",
    "PLATFORM_TRIPLET",
    "PIP_CONSTRAINT",
    "PYMAJOR",
    "PYMICRO",
    "PYMINOR",
    "PYO3_CROSS_INCLUDE_DIR",
    "PYO3_CROSS_LIB_DIR",
    "PYODIDE_EMSCRIPTEN_VERSION",
    "PYODIDE_JOBS",
    "PYODIDE_PACKAGE_ABI",
    "PYODIDE_ROOT",
    "PYTHON_ARCHIVE_SHA256",
    "PYTHON_ARCHIVE_URL",
    "PYTHONINCLUDE",
    "PYTHONPATH",
    "PYVERSION",
    "RUSTFLAGS",
    "RUST_TOOLCHAIN",
    "SIDE_MODULE_CFLAGS",
    "SIDE_MODULE_CXXFLAGS",
    "SIDE_MODULE_LDFLAGS",
    "STDLIB_MODULE_CFLAGS",
    "SYSCONFIGDATA_DIR",
    "SYSCONFIG_NAME",
    "TARGETINSTALLDIR",
    "WASM_LIBRARY_DIR",
    "CMAKE_TOOLCHAIN_FILE",
    "PYO3_CONFIG_FILE",
    "MESON_CROSS_FILE",
    "PKG_CONFIG_LIBDIR",
}


@dataclasses.dataclass(eq=False, order=False, kw_only=True)
class BuildArgs:
    """
    Common arguments for building a package.
    """

    pkgname: str = ""
    cflags: str = ""
    cxxflags: str = ""
    ldflags: str = ""
    target_install_dir: str = ""  # The path to the target Python installation
    host_install_dir: str = ""  # Directory for installing built host packages.
    builddir: str = ""  # The path to run pypa/build


def init_environment(*, quiet: bool = False) -> None:
    """
    Initialize Pyodide build environment.
    This function needs to be called before any other Pyodide build functions.

    Parameters
    ----------
    quiet
        If True, do not print any messages
    """

    # Already initialized
    if "PYODIDE_ROOT" in os.environ:
        return

    try:
        root = search_pyodide_root(Path.cwd())
    except FileNotFoundError:  # Not in Pyodide tree
        root = _init_xbuild_env(quiet=quiet)

    os.environ["PYODIDE_ROOT"] = str(root)


def _init_xbuild_env(*, quiet: bool = False) -> Path:
    """
    Initialize the build environment for out-of-tree builds.

    Parameters
    ----------
    quiet
        If True, do not print any messages

    Returns
    -------
        The path to the Pyodide root directory inside the xbuild environment
    """
    from . import install_xbuildenv  # avoid circular import

    # TODO: Do not hardcode the path
    # TODO: Add version numbers to the path
    xbuildenv_path = Path(".pyodide-xbuildenv").resolve()

    context = redirect_stdout(StringIO()) if quiet else nullcontext()
    with context:
        return install_xbuildenv.install(xbuildenv_path, download=True)


@functools.cache
def get_pyodide_root() -> Path:
    init_environment()
    return Path(os.environ["PYODIDE_ROOT"])


def search_pyodide_root(curdir: str | Path, *, max_depth: int = 10) -> Path:
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


def in_xbuildenv() -> bool:
    pyodide_root = get_pyodide_root()
    return pyodide_root.name == "pyodide-root"


@functools.cache
def get_build_environment_vars() -> dict[str, str]:
    """
    Get common environment variables for the in-tree and out-of-tree build.
    """
    env = _get_make_environment_vars().copy()

    # Allow users to overwrite the build environment variables by setting
    # host environment variables.
    # TODO: Add modifiable configuration file instead.
    # (https://github.com/pyodide/pyodide/pull/3737/files#r1161247201)
    env.update({key: os.environ[key] for key in BUILD_VARS if key in os.environ})
    env["PYODIDE"] = "1"

    tools_dir = Path(__file__).parent / "tools"

    if "CMAKE_TOOLCHAIN_FILE" not in env:
        env["CMAKE_TOOLCHAIN_FILE"] = str(
            tools_dir / "cmake/Modules/Platform/Emscripten.cmake"
        )

    if "PYO3_CONFIG_FILE" not in env:
        env["PYO3_CONFIG_FILE"] = str(tools_dir / "pyo3_config.ini")

    if "MESON_CROSS_FILE" not in env:
        env["MESON_CROSS_FILE"] = str(tools_dir / "emscripten.meson.cross")

    hostsitepackages = env["HOSTSITEPACKAGES"]
    pythonpath = [
        hostsitepackages,
    ]
    env["PYTHONPATH"] = ":".join(pythonpath)

    return env


def _get_make_environment_vars(*, pyodide_root: Path | None = None) -> dict[str, str]:
    """Load environment variables from Makefile.envs

    This allows us to set all build vars in one place

    Parameters
    ----------
    pyodide_root
        The root directory of the Pyodide repository. If None, this will be inferred.
    """

    PYODIDE_ROOT = get_pyodide_root() if pyodide_root is None else pyodide_root
    environment = {}
    result = subprocess.run(
        ["make", "-f", str(PYODIDE_ROOT / "Makefile.envs"), ".output_vars"],
        capture_output=True,
        text=True,
        env={"PYODIDE_ROOT": str(PYODIDE_ROOT)},
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


def get_build_flag(name: str) -> str:
    """
    Get a value of a build flag.
    """
    build_vars = get_build_environment_vars()
    if name not in build_vars:
        raise ValueError(f"Unknown build flag: {name}")

    return build_vars[name]


def get_pyversion_major() -> str:
    return get_build_flag("PYMAJOR")


def get_pyversion_minor() -> str:
    return get_build_flag("PYMINOR")


def get_pyversion_major_minor() -> str:
    return f"{get_pyversion_major()}.{get_pyversion_minor()}"


def get_pyversion() -> str:
    return f"python{get_pyversion_major_minor()}"


def get_hostsitepackages() -> str:
    return get_build_flag("HOSTSITEPACKAGES")


@functools.cache
def get_unisolated_packages() -> list[str]:
    PYODIDE_ROOT = get_pyodide_root()

    unisolated_file = PYODIDE_ROOT / "unisolated.txt"
    if unisolated_file.exists():
        # in xbuild env, read from file
        unisolated_packages = unisolated_file.read_text().splitlines()
    else:
        unisolated_packages = []
        recipe_dir = PYODIDE_ROOT / "packages"
        recipes = load_all_recipes(recipe_dir)
        for name, config in recipes.items():
            if config.build.cross_build_env:
                unisolated_packages.append(name)

    return unisolated_packages


def platform() -> str:
    emscripten_version = get_build_flag("PYODIDE_EMSCRIPTEN_VERSION")
    version = emscripten_version.replace(".", "_")
    return f"emscripten_{version}_wasm32"


def pyodide_tags() -> Iterator[Tag]:
    """
    Returns the sequence of tag triples for the Pyodide interpreter.

    The sequence is ordered in decreasing specificity.
    """
    PYMAJOR = get_pyversion_major()
    PYMINOR = get_pyversion_minor()
    PLATFORM = platform()
    python_version = (int(PYMAJOR), int(PYMINOR))
    yield from cpython_tags(platforms=[PLATFORM], python_version=python_version)
    yield from compatible_tags(platforms=[PLATFORM], python_version=python_version)
    # Following line can be removed once packaging 22.0 is released and we update to it.
    yield Tag(interpreter=f"cp{PYMAJOR}{PYMINOR}", abi="none", platform="any")


def replace_so_abi_tags(wheel_dir: Path) -> None:
    """Replace native abi tag with emscripten abi tag in .so file names"""
    import sysconfig

    build_soabi = sysconfig.get_config_var("SOABI")
    assert build_soabi
    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX")
    assert ext_suffix
    build_triplet = "-".join(build_soabi.split("-")[2:])
    host_triplet = get_build_flag("PLATFORM_TRIPLET")
    for file in wheel_dir.glob(f"**/*{ext_suffix}"):
        file.rename(file.with_name(file.name.replace(build_triplet, host_triplet)))


def emscripten_version() -> str:
    return get_build_flag("PYODIDE_EMSCRIPTEN_VERSION")


def get_emscripten_version_info() -> str:
    """Extracted for testing purposes."""
    return subprocess.run(["emcc", "-v"], capture_output=True, encoding="utf8").stderr


def check_emscripten_version() -> None:
    needed_version = emscripten_version()
    try:
        version_info = get_emscripten_version_info()
    except FileNotFoundError:
        raise RuntimeError(
            f"No Emscripten compiler found. Need Emscripten version {needed_version}"
        ) from None
    installed_version = None
    try:
        for x in reversed(version_info.partition("\n")[0].split(" ")):
            if re.match(r"[0-9]+\.[0-9]+\.[0-9]+", x):
                installed_version = x
                break
    except Exception:
        raise RuntimeError("Failed to determine Emscripten version.") from None
    if installed_version is None:
        raise RuntimeError("Failed to determine Emscripten version.")
    if installed_version != needed_version:
        raise RuntimeError(
            f"Incorrect Emscripten version {installed_version}. Need Emscripten version {needed_version}"
        )
