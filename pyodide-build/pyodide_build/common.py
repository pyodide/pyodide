# Common functions shared by other modules.
# Notes for contributors:
#   This module should not import any other modules from pyodide-build except logger to avoid circular imports.

import contextlib
import hashlib
import os
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
from zipfile import ZipFile

from packaging.tags import Tag
from packaging.utils import canonicalize_name as canonicalize_package_name
from packaging.utils import parse_wheel_filename

from .logger import logger


def xbuildenv_dirname() -> str:
    from . import __version__

    return f".pyodide-xbuildenv-{__version__}"


def find_matching_wheels(
    wheel_paths: Iterable[Path], supported_tags: Iterator[Tag]
) -> Iterator[Path]:
    """
    Returns the sequence wheels whose tags match the Pyodide interpreter.

    Parameters
    ----------
    wheel_paths
        A list of paths to wheels
    supported_tags
        A list of tags that the environment supports

    Returns
    -------
    The subset of wheel_paths that have tags that match the Pyodide interpreter.
    """
    wheel_paths = list(wheel_paths)
    wheel_tags_list: list[frozenset[Tag]] = []

    for wheel in wheel_paths:
        _, _, _, tags = parse_wheel_filename(wheel.name)
        wheel_tags_list.append(tags)

    for supported_tag in supported_tags:
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


def _environment_substitute_str(
    string: str, env: Mapping[str, str] | None = None
) -> str:
    """
    Substitute $(VAR) in string with the value of the environment variable VAR.

    Parameters
    ----------
    string
        A string

    env
        A dictionary of environment variables. If None, use os.environ.

    Returns
    -------
    A string with the substitutions applied.
    """
    if env is None:
        env = dict(os.environ)

    for e_name, e_value in env.items():
        string = string.replace(f"$({e_name})", e_value)

    return string


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
            value = _environment_substitute_str(value, env)
        subbed_args[arg] = value
    return subbed_args


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
        with (
            zipfile.ZipFile(input_path) as fh_zip_in,
            zipfile.ZipFile(
                archive_path,
                "w",
                compression=compression,
                compresslevel=compression_level,
            ) as fh_zip_out,
        ):
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


def unpack_wheel(wheel_path: Path, target_dir: Path | None = None) -> None:
    if target_dir is None:
        target_dir = wheel_path.parent
    result = subprocess.run(
        [sys.executable, "-m", "wheel", "unpack", wheel_path, "-d", target_dir],
        check=False,
        encoding="utf-8",
    )
    if result.returncode != 0:
        logger.error(f"ERROR: Unpacking wheel {wheel_path.name} failed")
        exit_with_stdio(result)


def pack_wheel(wheel_dir: Path, target_dir: Path | None = None) -> None:
    if target_dir is None:
        target_dir = wheel_dir.parent
    result = subprocess.run(
        [sys.executable, "-m", "wheel", "pack", wheel_dir, "-d", target_dir],
        check=False,
        encoding="utf-8",
    )
    if result.returncode != 0:
        logger.error(f"ERROR: Packing wheel {wheel_dir} failed")
        exit_with_stdio(result)


@contextmanager
def modify_wheel(wheel: Path) -> Iterator[Path]:
    """Unpacks the wheel into a temp directory and yields the path to the
    unpacked directory.

    The body of the with block is expected to inspect the wheel contents and
    possibly change it. If the body of the "with" block is successful, on
    exiting the with block the wheel contents are replaced with the updated
    contents of unpacked directory. If an exception is raised, then the original
    wheel is left unchanged.
    """
    with TemporaryDirectory() as temp_dir:
        unpack_wheel(wheel, Path(temp_dir))
        name, ver, _ = wheel.name.split("-", 2)
        wheel_dir_name = f"{name}-{ver}"
        wheel_dir = Path(temp_dir) / wheel_dir_name
        yield wheel_dir
        wheel.unlink()
        pack_wheel(wheel_dir, wheel.parent)


def retag_wheel(wheel_path: Path, platform: str) -> Path:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "wheel",
            "tags",
            wheel_path,
            "--platform-tag",
            platform,
            "--remove",
        ],
        check=False,
        encoding="utf-8",
        capture_output=True,
    )
    if result.returncode != 0:
        logger.error(f"ERROR: Retagging wheel {wheel_path} to {platform} failed")
        exit_with_stdio(result)
    return wheel_path.parent / result.stdout.splitlines()[-1].strip()


def extract_wheel_metadata_file(wheel_path: Path, output_path: Path) -> None:
    """Extracts the METADATA file from the given wheel and writes it to the
    output path.

    Raises a RuntimeError if the METADATA file does not exist.

    For a wheel called "NAME-VERSION-...", the METADATA file is expected to be
    found in a directory inside the wheel archive, whose name starts with NAME
    and ends with ".dist-info". See:
    https://packaging.python.org/en/latest/specifications/binary-distribution-format/#file-contents
    """
    with ZipFile(wheel_path, mode="r") as wheel:
        pkg_name = wheel_path.name.split("-", 1)[0]
        dist_info_dir = get_wheel_dist_info_dir(wheel, pkg_name)
        metadata_path = f"{dist_info_dir}/METADATA"
        try:
            wheel.getinfo(metadata_path).filename = output_path.name
            wheel.extract(metadata_path, output_path.parent)
        except KeyError as err:
            raise RuntimeError(f"METADATA file not found for {pkg_name}") from err


def get_wheel_dist_info_dir(wheel: ZipFile, pkg_name: str) -> str:
    """Returns the path of the contained .dist-info directory.

    Raises a RuntimeError if the directory is not found, more than
    one is found, or it does not match the provided `pkg_name`.

    Adapted from:
    https://github.com/pypa/pip/blob/ea727e4d6ab598f34f97c50a22350febc1214a97/src/pip/_internal/utils/wheel.py#L38
    """

    # Zip file path separators must be /
    subdirs = {name.split("/", 1)[0] for name in wheel.namelist()}
    info_dirs = [subdir for subdir in subdirs if subdir.endswith(".dist-info")]

    if len(info_dirs) == 0:
        raise RuntimeError(f".dist-info directory not found for {pkg_name}")

    if len(info_dirs) > 1:
        raise RuntimeError(
            f"multiple .dist-info directories found for {pkg_name}: {', '.join(info_dirs)}"
        )

    (info_dir,) = info_dirs

    info_dir_name = canonicalize_package_name(info_dir)
    canonical_name = canonicalize_package_name(pkg_name)

    if not info_dir_name.startswith(canonical_name):
        raise RuntimeError(
            f".dist-info directory {info_dir!r} does not start with {canonical_name!r}"
        )

    return info_dir


def check_wasm_magic_number(file_path: Path) -> bool:
    WASM_BINARY_MAGIC = b"\0asm"
    with file_path.open(mode="rb") as file:
        return file.read(4) == WASM_BINARY_MAGIC
