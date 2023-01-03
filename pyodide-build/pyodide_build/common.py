import contextlib
import functools
import os
import re
import shutil
import subprocess
import sys
import textwrap
import zipfile
from collections import deque
from collections.abc import Generator, Iterable, Iterator, Mapping
from pathlib import Path
from typing import NoReturn

import tomli
from packaging.tags import Tag, compatible_tags, cpython_tags
from packaging.utils import parse_wheel_filename

from .io import MetaConfig

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
    "CARGO_HOME",
    "RUSTFLAGS",
    "PYODIDE_EMSCRIPTEN_VERSION",
    "PLATFORM_TRIPLET",
    "SYSCONFIGDATA_DIR",
}


def emscripten_version() -> str:
    return get_make_flag("PYODIDE_EMSCRIPTEN_VERSION")


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


def platform() -> str:
    emscripten_version = get_make_flag("PYODIDE_EMSCRIPTEN_VERSION")
    version = emscripten_version.replace(".", "_")
    return f"emscripten_{version}_wasm32"


def pyodide_tags() -> Iterator[Tag]:
    """
    Returns the sequence of tag triples for the Pyodide interpreter.

    The sequence is ordered in decreasing specificity.
    """
    PYMAJOR = get_make_flag("PYMAJOR")
    PYMINOR = get_make_flag("PYMINOR")
    PLATFORM = platform()
    python_version = (int(PYMAJOR), int(PYMINOR))
    yield from cpython_tags(platforms=[PLATFORM], python_version=python_version)
    yield from compatible_tags(platforms=[PLATFORM], python_version=python_version)
    # Following line can be removed once packaging 22.0 is released and we update to it.
    yield Tag(interpreter=f"cp{PYMAJOR}{PYMINOR}", abi="none", platform="any")


def find_matching_wheels(wheel_paths: Iterable[Path]) -> Iterator[Path]:
    """
    Returns the sequence wheels whose tags match the Pyodide interpreter.

    Parameters
    ----------
    wheel_paths
        A list of paths to wheels

    Returns
    -------
    The subset of wheel_paths that have tags that match the Pyodide interpreter.
    """
    wheel_paths = list(wheel_paths)
    wheel_tags_list: list[frozenset[Tag]] = []
    for wheel in wheel_paths:
        _, _, _, tags = parse_wheel_filename(wheel.name)
        wheel_tags_list.append(tags)
    for supported_tag in pyodide_tags():
        for wheel_path, wheel_tags in zip(wheel_paths, wheel_tags_list):
            if supported_tag in wheel_tags:
                yield wheel_path


def parse_top_level_import_name(whlfile: Path) -> list[str] | None:
    """
    Parse the top-level import names from a wheel file.
    """

    if not whlfile.name.endswith(".whl"):
        raise RuntimeError(f"{whlfile} is not a wheel file.")

    whlzip = zipfile.Path(whlfile)

    def _valid_package_name(dirname: str) -> bool:
        return all([invalid_chr not in dirname for invalid_chr in ".- "])

    def _has_python_file(subdir: zipfile.Path) -> bool:
        queue = deque([subdir])
        while queue:
            nested_subdir = queue.pop()
            for subfile in nested_subdir.iterdir():
                if subfile.is_file() and subfile.name.endswith(".py"):
                    return True
                elif subfile.is_dir() and _valid_package_name(subfile.name):
                    queue.append(subfile)

        return False

    # If there is no top_level.txt file, we will find top level imports by
    # 1) a python file on a top-level directory
    # 2) a sub directory with __init__.py
    # following: https://github.com/pypa/setuptools/blob/d680efc8b4cd9aa388d07d3e298b870d26e9e04b/setuptools/discovery.py#L122
    top_level_imports = []
    for subdir in whlzip.iterdir():
        if subdir.is_file() and subdir.name.endswith(".py"):
            top_level_imports.append(subdir.name[:-3])
        elif subdir.is_dir() and _valid_package_name(subdir.name):
            if _has_python_file(subdir):
                top_level_imports.append(subdir.name)

    if not top_level_imports:
        print(f"Warning: failed to parse top level import name from {whlfile}.")
        return None

    return top_level_imports


ALWAYS_PACKAGES = {
    "pyparsing",
    "packaging",
    "micropip",
    "distutils",
    "test",
    "ssl",
    "lzma",
    "sqlite3",
    "hashlib",
}

CORE_PACKAGES = {
    "micropip",
    "pyparsing",
    "pytz",
    "packaging",
    "Jinja2",
    "regex",
    "fpcast-test",
    "sharedlib-test-py",
    "cpp-exceptions-test",
    "pytest",
    "tblib",
}

CORE_SCIPY_PACKAGES = {
    "numpy",
    "scipy",
    "pandas",
    "matplotlib",
    "scikit-learn",
    "joblib",
    "pytest",
}


def _parse_package_subset(query: str | None) -> set[str]:
    """Parse the list of packages specified with PYODIDE_PACKAGES env var.

    Also add the list of mandatory packages: ["pyparsing", "packaging",
    "micropip"]

    Supports following meta-packages,
     - 'core': corresponds to packages needed to run the core test suite
       {"micropip", "pyparsing", "pytz", "packaging", "Jinja2", "fpcast-test"}. This is the default option
       if query is None.
     - 'min-scipy-stack': includes the "core" meta-package as well as some of the
       core packages from the scientific python stack and their dependencies:
       {"numpy", "scipy", "pandas", "matplotlib", "scikit-learn", "joblib", "pytest"}.
       This option is non exhaustive and is mainly intended to make build faster
       while testing a diverse set of scientific packages.
     - '*': corresponds to all packages (returns None)

    Note: None as input is equivalent to PYODIDE_PACKAGES being unset and leads
    to only the core packages being built.

    Returns:
      a set of package names to build or None (build all packages).
    """
    if query is None:
        query = "core"

    packages = {el.strip() for el in query.split(",")}
    packages.update(ALWAYS_PACKAGES)
    # handle meta-packages
    if "core" in packages:
        packages |= CORE_PACKAGES
        packages.discard("core")
    if "min-scipy-stack" in packages:
        packages |= CORE_PACKAGES | CORE_SCIPY_PACKAGES
        packages.discard("min-scipy-stack")

    packages.discard("")
    return packages


def get_make_flag(name: str) -> str:
    """Get flags from makefile.envs.

    For building packages we currently use:
        SIDE_MODULE_LDFLAGS
        SIDE_MODULE_CFLAGS
        SIDE_MODULE_CXXFLAGS
    """
    return get_make_environment_vars()[name]


def get_pyversion() -> str:
    PYMAJOR = get_make_flag("PYMAJOR")
    PYMINOR = get_make_flag("PYMINOR")
    return f"python{PYMAJOR}.{PYMINOR}"


def get_hostsitepackages() -> str:
    return get_make_flag("HOSTSITEPACKAGES")


@functools.cache
def get_make_environment_vars() -> dict[str, str]:
    """Load environment variables from Makefile.envs

    This allows us to set all build vars in one place"""

    PYODIDE_ROOT = get_pyodide_root()
    environment = {}
    result = subprocess.run(
        ["make", "-f", str(PYODIDE_ROOT / "Makefile.envs"), ".output_vars"],
        capture_output=True,
        text=True,
    )
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
                configs = tomli.load(f)
        except tomli.TOMLDecodeError as e:
            raise ValueError(f"Could not parse {pyproject_file}.") from e

        if "tool" in configs and "pyodide" in configs["tool"]:
            return base

    raise FileNotFoundError(
        "Could not find Pyodide root directory. If you are not in the Pyodide directory, set `PYODIDE_ROOT=<pyodide-root-directory>`."
    )


def init_environment() -> None:
    if os.environ.get("__LOADED_PYODIDE_ENV"):
        return
    os.environ["__LOADED_PYODIDE_ENV"] = "1"
    # If we are building docs, we don't need to know the PYODIDE_ROOT
    if "sphinx" in sys.modules:
        os.environ["PYODIDE_ROOT"] = ""

    if "PYODIDE_ROOT" in os.environ:
        os.environ["PYODIDE_ROOT"] = str(Path(os.environ["PYODIDE_ROOT"]).resolve())
    else:
        os.environ["PYODIDE_ROOT"] = str(search_pyodide_root(os.getcwd()))

    os.environ.update(get_make_environment_vars())
    try:
        hostsitepackages = get_hostsitepackages()
        pythonpath = [
            hostsitepackages,
        ]
        os.environ["PYTHONPATH"] = ":".join(pythonpath)
    except KeyError:
        pass
    os.environ["BASH_ENV"] = ""
    get_unisolated_packages()


@functools.cache
def get_pyodide_root() -> Path:
    init_environment()
    return Path(os.environ["PYODIDE_ROOT"])


@functools.cache
def get_unisolated_packages() -> list[str]:
    import json

    if "UNISOLATED_PACKAGES" in os.environ:
        return json.loads(os.environ["UNISOLATED_PACKAGES"])
    PYODIDE_ROOT = get_pyodide_root()
    unisolated_file = PYODIDE_ROOT / "unisolated.txt"
    if unisolated_file.exists():
        # in xbuild env, read from file
        unisolated_packages = unisolated_file.read_text().splitlines()
    else:
        unisolated_packages = []
        for pkg in (PYODIDE_ROOT / "packages").glob("*/meta.yaml"):
            try:
                config = MetaConfig.from_yaml(pkg)
            except Exception as e:
                raise ValueError(f"Could not parse {pkg}.") from e
            if config.build.cross_build_env:
                unisolated_packages.append(config.package.name)
    os.environ["UNISOLATED_PACKAGES"] = json.dumps(unisolated_packages)
    return unisolated_packages


@contextlib.contextmanager
def replace_env(build_env: Mapping[str, str]) -> Generator[None, None, None]:
    old_environ = dict(os.environ)
    os.environ.clear()
    os.environ.update(build_env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_environ)


def exit_with_stdio(result: subprocess.CompletedProcess[str]) -> NoReturn:
    if result.stdout:
        print("  stdout:")
        print(textwrap.indent(result.stdout, "    "))
    if result.stderr:
        print("  stderr:")
        print(textwrap.indent(result.stderr, "    "))
    raise SystemExit(result.returncode)


def in_xbuildenv() -> bool:
    pyodide_root = get_pyodide_root()
    return pyodide_root.name == "pyodide-root"


def find_missing_executables(executables: list[str]) -> list[str]:
    return list(filter(lambda exe: shutil.which(exe) is None, executables))
