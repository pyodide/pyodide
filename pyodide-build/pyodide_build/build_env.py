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

from packaging.tags import Tag, compatible_tags, cpython_tags

from . import __version__
from .common import search_pyproject_toml, xbuildenv_dirname
from .config import ConfigManager
from .recipe import load_all_recipes

RUST_BUILD_PRELUDE = """
rustup toolchain install ${RUST_TOOLCHAIN} && rustup default ${RUST_TOOLCHAIN}
rustup target add wasm32-unknown-emscripten --toolchain ${RUST_TOOLCHAIN}
"""


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

    root = search_pyodide_root(Path.cwd())
    if not root:  # Not in Pyodide tree
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
    from .xbuildenv import CrossBuildEnvManager  # avoid circular import

    xbuildenv_path = Path(xbuildenv_dirname()).resolve()
    context = redirect_stdout(StringIO()) if quiet else nullcontext()
    with context:
        manager = CrossBuildEnvManager(xbuildenv_path)
        if manager.current_version is None:
            manager.install()

        return manager.pyodide_root


@functools.cache
def get_pyodide_root() -> Path:
    init_environment()
    return Path(os.environ["PYODIDE_ROOT"])


def search_pyodide_root(curdir: str | Path, *, max_depth: int = 10) -> Path | None:
    """
    Recursively search for the root of the Pyodide repository,
    by looking for the pyproject.toml file in the parent directories
    which contains [tool.pyodide] section.
    """
    pyproject_path, pyproject_file = search_pyproject_toml(curdir, max_depth)

    if pyproject_path is None or pyproject_file is None:
        return None

    if "tool" in pyproject_file and "_pyodide" in pyproject_file["tool"]:
        return pyproject_path.parent

    return None


def in_xbuildenv() -> bool:
    pyodide_root = get_pyodide_root()
    return pyodide_root.name == "pyodide-root"


@functools.cache
def get_build_environment_vars(pyodide_root: Path) -> dict[str, str]:
    """
    Get common environment variables for the in-tree and out-of-tree build.
    """
    config_manager = ConfigManager(pyodide_root)
    env = config_manager.to_env()

    env.update(
        {
            # This environment variable is used for packages to detect if they are built
            # for pyodide during build time
            "PYODIDE": "1",
            # This is the legacy environment variable used for the aforementioned purpose
            "PYODIDE_PACKAGE_ABI": "1",
            "PYTHONPATH": env["HOSTSITEPACKAGES"],
        }
    )

    return env


def get_build_flag(name: str) -> str:
    """
    Get a value of a build flag.
    """
    pyodide_root = get_pyodide_root()
    build_vars = get_build_environment_vars(pyodide_root)
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


def wheel_platform() -> str:
    abi_version = get_build_flag("PYODIDE_ABI_VERSION")
    return f"pyodide_{abi_version}_wasm32"


def pyodide_tags() -> Iterator[Tag]:
    """
    Returns the sequence of tag triples for the Pyodide interpreter.

    The sequence is ordered in decreasing specificity.
    """
    PYMAJOR = get_pyversion_major()
    PYMINOR = get_pyversion_minor()
    PLATFORMS = [platform(), wheel_platform()]
    python_version = (int(PYMAJOR), int(PYMINOR))
    yield from cpython_tags(platforms=PLATFORMS, python_version=python_version)
    yield from compatible_tags(platforms=PLATFORMS, python_version=python_version)
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


def local_versions() -> dict[str, str]:
    """
    Returns the versions of the local Python interpreter and the pyodide-build.
    This information is used for checking compatibility with the cross-build environment.
    """
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "pyodide-build": __version__,
        # "emscripten": "TODO"
    }
