#!/usr/bin/env python

# Adapted from: https://github.com/python/cpython/blob/main/Tools/wasm/wasm_assets.py
"""Create a WASM asset bundle directory structure.
The WASM asset bundles are pre-loaded by the final WASM build. The bundle
contains:
- a stripped down, pyc-only stdlib zip file, e.g. {PREFIX}/lib/python{version}.zip
- os.py as marker module {PREFIX}/lib/python3.11/os.py
- empty lib-dynload directory, to make sure it is copied into the bundle {PREFIX}/lib/python3.11/lib-dynload/.empty
"""

import argparse
import os
import pathlib
import shutil
import tempfile
import zipfile
from pathlib import Path

# This files are removed from the stdlib by default
REMOVED_FILES = (
    # package management
    "ensurepip/",
    "venv/",
    # build system
    "lib2to3/",
    # other platforms
    "_osx_support.py",
    # Not supported by browser
    "curses/",
    "dbm/",
    "idlelib/",
    "tkinter/",
    "turtle.py",
    "turtledemo",
    "webbrowser.py",
)

# This files are unvendored from the stdlib by default
UNVENDORED_FILES = (
    "test/",
    "distutils/",
    "sqlite3",
    "ssl.py",
    "lzma.py",
)

# TODO: These modules have test directory which we unvendors it separately.
#       So we should not pack them into the zip file in order to make e.g. import ctypes.test work.
#       Note that all these tests are moved to the subdirectory of `test` module in upstream CPython 3.12.0a1.
#       So we don't need this after we upgrade to 3.12.0
NOT_ZIPPED_FILES = ("ctypes/", "unittest/")


class PyZipFileShortTraceback(zipfile.PyZipFile):
    """
    This class is for creating .pyc files with shortened traceback.

    With PyZipFile:

    Traceback (most recent call last):
        File "/src/cpython/installs/python-3.10.2/lib/python3.10/pathlib.py", line 1152, in write_text
        File "/src/cpython/installs/python-3.10.2/lib/python3.10/pathlib.py", line 1117, in open

    With this class:

    Traceback (most recent call last):
        File "pathlib.py", line 1152, in write_text
        File "pathlib.py", line 1117, in open
    """

    def __init__(
        self,
        file,
        mode="r",
        compression=zipfile.ZIP_STORED,
        allowZip64=True,
        optimize=-1,
        basedir=None,
    ):
        super().__init__(file, mode, compression, allowZip64, optimize)
        self.pyc_dir = Path(tempfile.mkdtemp())
        self.base_dir = basedir

    def __del__(self):
        super().__del__()
        shutil.rmtree(self.pyc_dir)

    def _get_codename(self, pathname, basename):
        """Return (filename, archivename) for the path.
        Given a module name path, return the correct file path and
        archive name, compiling if necessary.  For example, given
        /python/lib/string, return (/python/lib/string.pyc, string).
        """

        def _compile(file, optimize=-1):
            import py_compile

            if self.debug:
                print("Compiling", file)

            rel_path = Path(file).relative_to(self.base_dir)
            compile_path_full = self.pyc_dir / rel_path.with_suffix(".pyc")
            py_compile.compile(
                file,
                cfile=str(compile_path_full),
                dfile=str(rel_path),
                doraise=True,
                optimize=optimize,
            )

            return compile_path_full

        file_py = pathname + ".py"
        file_pyc = _compile(file_py, optimize=self._optimize)

        archivename = os.path.split(file_pyc)[1]
        if basename:
            archivename = f"{basename}/{archivename}"

        return (file_pyc, archivename)


def create_stdlib_zip(
    args: argparse.Namespace,
    *,
    optimize: int = 0,
) -> None:
    with PyZipFileShortTraceback(
        args.wasm_stdlib_zip,
        mode="w",
        compression=args.compression,
        optimize=optimize,
        basedir=args.srcdir_lib,
    ) as pzf:
        if args.compresslevel is not None:
            pzf.compresslevel = args.compresslevel
        for entry in sorted(args.srcdir_lib.iterdir()):
            if entry.name == "__pycache__":
                continue
            if entry in args.omit_files_absolute:
                continue
            if entry.name.endswith(".py") or entry.is_dir():
                # writepy() writes .pyc files (bytecode).
                pzf.writepy(entry)


def path(val: str) -> pathlib.Path:
    return pathlib.Path(val).absolute()


parser = argparse.ArgumentParser()
parser.add_argument(
    "--buildroot",
    help="absolute path to build root",
    default=pathlib.Path(__file__).resolve().parent,
    type=path,
)
parser.add_argument(
    "-o",
    "--out",
    default=pathlib.Path("stdlib_zip"),
    type=path,
)

parser.add_argument(
    "--python-version",
    help="Python version in {major}.{minor}.{patch} format",
    default="3.10.2",
)


def main():
    args = parser.parse_args()

    version = args.python_version
    version_major, version_minor, version_patch = version.split(".")

    # source directory
    SRCDIR = pathlib.Path(__file__).parent / "installs" / f"python-{version}"
    SRCDIR_LIB = SRCDIR / "lib" / f"python{version_major}.{version_minor}"

    # Library directory relative to $(prefix).
    WASM_LIB = pathlib.PurePath("lib")
    WASM_STDLIB_ZIP = WASM_LIB / f"python{version_major}{version_minor}.zip"
    WASM_STDLIB = WASM_LIB / f"python{version_major}.{version_minor}"
    WASM_DYNLOAD = WASM_STDLIB / "lib-dynload"
    WASM_SITEPACKAGES = WASM_STDLIB / "site-packages"

    args.srcdir = SRCDIR
    args.srcdir_lib = SRCDIR_LIB
    args.wasm_root = args.out.absolute()
    args.wasm_stdlib_zip = args.wasm_root / WASM_STDLIB_ZIP
    args.wasm_stdlib = args.wasm_root / WASM_STDLIB
    args.wasm_dynload = args.wasm_root / WASM_DYNLOAD
    args.wasm_sitepackages = args.wasm_root / WASM_SITEPACKAGES

    # bpo-17004: zipimport supports only zlib compression.
    # Emscripten ZIP_STORED + -sLZ4=1 linker flags results in larger file.
    args.compression = zipfile.ZIP_DEFLATED
    args.compresslevel = 9

    omit_files = list(REMOVED_FILES)
    omit_files.extend(UNVENDORED_FILES)
    omit_files.extend(NOT_ZIPPED_FILES)

    args.omit_files_absolute = {args.srcdir_lib / name for name in omit_files}

    # Empty, unused directory for dynamic libs, but required for site initialization.
    args.wasm_dynload.mkdir(parents=True, exist_ok=True)
    marker = args.wasm_dynload / ".empty"
    marker.touch()

    args.wasm_sitepackages.mkdir(parents=True, exist_ok=True)
    marker = args.wasm_sitepackages / ".keep"
    marker.touch()

    # os.py is a marker for finding the correct lib directory.
    shutil.copy(args.srcdir_lib / "os.py", args.wasm_stdlib)
    for not_zipped_dir in NOT_ZIPPED_FILES:
        shutil.copytree(
            args.srcdir_lib / not_zipped_dir,
            args.wasm_stdlib / not_zipped_dir,
            ignore=shutil.ignore_patterns("test", "__pycache__"),
        )
    # The rest of stdlib that's useful in a WASM context.
    create_stdlib_zip(args)
    size = round(args.wasm_stdlib_zip.stat().st_size / 1024**2, 2)
    parser.exit(0, f"Created {args.wasm_stdlib_zip} ({size} MiB)\n")


if __name__ == "__main__":
    main()
