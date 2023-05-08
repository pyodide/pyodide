import contextlib
import functools
import hashlib
import os
import re
import shutil
import subprocess
import sys
import textwrap
import zipfile
from collections import deque
from collections.abc import Generator, Iterable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NoReturn

if sys.version_info < (3, 11, 0):
    import tomli as tomllib
else:
    import tomllib

from packaging.tags import Tag, compatible_tags, cpython_tags
from packaging.utils import parse_wheel_filename

from .logger import logger
from .recipe import load_all_recipes

BUILD_VARS: set[str] = {
    "PATH",
    "PYTHONPATH",
    "PYODIDE_JOBS",
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
        for wheel_path, wheel_tags in zip(wheel_paths, wheel_tags_list, strict=True):
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
        logger.warning(
            f"WARNING: failed to parse top level import name from {whlfile}."
        )
        return None

    return top_level_imports


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


def _get_make_environment_vars() -> dict[str, str]:
    """Load environment variables from Makefile.envs

    This allows us to set all build vars in one place"""

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


def environment_substitute_args(
    args: dict[str, str], env: dict[str, str] | None = None
) -> dict[str, Any]:
    """
    Substitute $(VAR) in args with the value of the environment variable VAR.

    Parameters
    ----------
    args
        A dictionary of arguments

    env
        A dictionary of environment variables. If None, use os.environ.

    Returns
    -------
    A dictionary of arguments with the substitutions applied.
    """
    if env is None:
        env = dict(os.environ)
    subbed_args = {}
    for arg, value in args.items():
        if isinstance(value, str):
            for e_name, e_value in env.items():
                value = value.replace(f"$({e_name})", e_value)
        subbed_args[arg] = value
    return subbed_args


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


@functools.cache
def get_pyodide_root() -> Path:
    init_environment()
    return Path(os.environ["PYODIDE_ROOT"])


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
        logger.error("  stdout:")
        logger.error(textwrap.indent(result.stdout, "    "))
    if result.stderr:
        logger.error("  stderr:")
        logger.error(textwrap.indent(result.stderr, "    "))
    raise SystemExit(result.returncode)


def in_xbuildenv() -> bool:
    pyodide_root = get_pyodide_root()
    return pyodide_root.name == "pyodide-root"


def find_missing_executables(executables: list[str]) -> list[str]:
    return list(filter(lambda exe: shutil.which(exe) is None, executables))


@contextmanager
def chdir(new_dir: Path) -> Generator[None, None, None]:
    orig_dir = Path.cwd()
    try:
        os.chdir(new_dir)
        yield
    finally:
        os.chdir(orig_dir)


def set_build_environment(env: dict[str, str]) -> None:
    """Assign build environment variables to env.

    Sets common environment between in tree and out of tree package builds.
    """
    env.update({key: os.environ[key] for key in BUILD_VARS if key in os.environ})
    env["PYODIDE"] = "1"

    pkg_config_parts = []
    if "WASM_PKG_CONFIG_PATH" in os.environ:
        pkg_config_parts.append(env["WASM_PKG_CONFIG_PATH"])
    if "PKG_CONFIG_PATH" in os.environ:
        pkg_config_parts.append(os.environ["PKG_CONFIG_PATH"])
    env["PKG_CONFIG_PATH"] = ":".join(pkg_config_parts)

    tools_dir = Path(__file__).parent / "tools"

    env["CMAKE_TOOLCHAIN_FILE"] = str(
        tools_dir / "cmake/Modules/Platform/Emscripten.cmake"
    )
    env["PYO3_CONFIG_FILE"] = str(tools_dir / "pyo3_config.ini")


def get_num_cores() -> int:
    """
    Return the number of CPUs the current process can use.
    If the number of CPUs cannot be determined, return 1.
    """
    import loky

    return loky.cpu_count()


def make_zip_archive(
    archive_path: Path,
    input_dir: Path,
    compression_level: int = 6,
) -> None:
    """Create a zip archive out of a input folder

    Parameters
    ----------
    archive_path
       Path to the zip file that will be created
    input_dir
       input dir to compress
    compression_level
       compression level of the resulting zip file.
    """
    if compression_level > 0:
        compression = zipfile.ZIP_DEFLATED
    else:
        compression = zipfile.ZIP_STORED

    with zipfile.ZipFile(
        archive_path, "w", compression=compression, compresslevel=compression_level
    ) as zf:
        for file in input_dir.rglob("*"):
            zf.write(file, file.relative_to(input_dir))


def repack_zip_archive(archive_path: Path, compression_level: int = 6) -> None:
    """Repack zip archive with a different compression level"""
    if compression_level > 0:
        compression = zipfile.ZIP_DEFLATED
    else:
        compression = zipfile.ZIP_STORED

    with TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / archive_path.name
        shutil.move(archive_path, input_path)
        with zipfile.ZipFile(input_path) as fh_zip_in, zipfile.ZipFile(
            archive_path, "w", compression=compression, compresslevel=compression_level
        ) as fh_zip_out:
            for name in fh_zip_in.namelist():
                fh_zip_out.writestr(name, fh_zip_in.read(name))


def _get_sha256_checksum(archive: Path) -> str:
    """Compute the sha256 checksum of a file

    Parameters
    ----------
    archive
        the path to the archive we wish to checksum

    Returns
    -------
    checksum
         sha256 checksum of the archive
    """
    CHUNK_SIZE = 1 << 16
    h = hashlib.sha256()
    with open(archive, "rb") as fd:
        while True:
            chunk = fd.read(CHUNK_SIZE)
            h.update(chunk)
            if len(chunk) < CHUNK_SIZE:
                break
    return h.hexdigest()
