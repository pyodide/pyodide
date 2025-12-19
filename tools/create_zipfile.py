#!/usr/bin/env python3
import re
import zipfile
from pathlib import Path
import shutil
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory


def default_filterfunc(
    root: Path, excludes: list[str], stubs: list[str], verbose: bool = False
) -> Callable[[str, list[str]], set[str]]:
    """
    The default filter function used by `create_zipfile`.

    This function filters out several modules that are:

    - not supported in Pyodide due to browser limitations (e.g. `tkinter`)
    - unvendored from the standard library (e.g. `sqlite3`)
    """

    def _should_skip(path: Path) -> bool:
        """Skip common files that are not needed in the zip file."""
        name = path.name

        if path.is_dir() and name in ("__pycache__", "dist"):
            return True

        if path.is_dir() and name.endswith((".egg-info", ".dist-info")):
            return True

        if path.is_file() and name in (
            "LICENSE",
            "LICENSE.txt",
            "setup.py",
            ".gitignore",
        ):
            return True

        if path.is_file() and name.endswith(("pyi", "toml", "cfg", "md", "rst")):
            return True

        return False

    def filterfunc(path: Path | str, names: list[str]) -> set[str]:
        filtered_files = {(root / f).resolve() for f in excludes}

        # We have JS implementations of these modules, so we don't need to
        # include the Python ones. Checking the name of the root directory
        # is a bit of a hack, but it works...
        if root.name.startswith("python3"):
            filtered_files.update({root / f for f in stubs})

        path = Path(path).resolve()

        if _should_skip(path):
            return set(names)

        _names = []
        for name in names:
            fullpath = path / name

            if _should_skip(fullpath) or fullpath in filtered_files:
                if verbose:
                    print(f"Skipping {fullpath}")

                _names.append(name)

        return set(_names)

    return filterfunc


def create_zipfile(
    libdirs: list[Path],
    excludes: list[str] | None = None,
    stubs: list[str] | None = None,
    output: Path | str = "python",
    filterfunc: Callable[[str, list[str]], set[str]] | None = None,
    compression_level: int = 6,
) -> None:
    """
    Bundle Python standard libraries into a zip file.

    The basic idea of this function is similar to the standard library's
    {ref}`zipfile.PyZipFile` class.

    However, we need some additional functionality for Pyodide. For example:

    - We need to remove some unvendored modules, e.g. `sqlite3`
    - We need an option to "not" compile the files in the zip file

    hence this function.

    Parameters
    ----------
    libdirs
        List of paths to the directory containing the Python standard library or extra packages.

    excludes
        List of files to exclude from the zip file.

    stubs
        List of files that are replaced by JS implementations.

    output
        Path to the output zip file. Defaults to python.zip.

    filterfunc
        A function that filters the files to be included in the zip file.
        This function will be passed to {ref}`shutil.copytree` 's ignore argument.
        By default, Pyodide's default filter function is used.

    compression_level
        Level of zip compression to apply. 0 means no compression. If a strictly
        positive integer is provided, ZIP_DEFLATED option is used.

    Returns
    -------
    BytesIO
        A BytesIO object containing the zip file.
    """

    archive = Path(output)
    excludes = excludes or []
    stubs = stubs or []

    with TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)

        for libdir in libdirs:
            libdir = Path(libdir)

            if filterfunc is None:
                _filterfunc = default_filterfunc(libdir, excludes, stubs)

            shutil.copytree(libdir, temp_dir, ignore=_filterfunc, dirs_exist_ok=True)

        make_zip_archive(
            archive,
            temp_dir,
            compression_level=compression_level,
        )

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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Create a zip file containing the Python standard library."
    )
    parser.add_argument(
        "libdirs",
        nargs="+",
        help="List of paths to the directory containing the Python standard library or extra packages.",
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="List of files to exclude from the zip file.",
    )
    parser.add_argument(
        "--stub",
        default="",
        help="List of files that are replaced by JS implementations.",
    )
    parser.add_argument(
        "--output",
        default="python.zip",
        help="Path to the output zip file. Defaults to python.zip.",
    )
    parser.add_argument(
        "--compression-level",
        type=int,
        default=6,
        help="Level of zip compression to apply. 0 means no compression. Defaults to 6.",
    )

    args = parser.parse_args()

    # Convert the comma / space separated strings to lists
    excludes = [
        item.strip() for item in re.split(r",|\s", args.exclude) if item.strip() != ""
    ]
    stubs = [item.strip() for item in re.split(r",|\s", args.stub) if item.strip() != ""]

    create_zipfile(
        [Path(libdir) for libdir in args.libdirs],
        excludes=excludes,
        stubs=stubs,
        output=Path(args.output),
        compression_level=args.compression_level,
    )