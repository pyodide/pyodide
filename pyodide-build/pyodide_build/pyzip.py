import shutil
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

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


def default_filterfunc(
    root: Path, verbose: bool = False
) -> Callable[[str, list[str]], set[str]]:
    """
    The default filter function used by `create_zipfile`.

    This function filters out several modules that are:

    - not supported in Pyodide due to browser limitations (e.g. `tkinter`)
    - unvendored from the standard library (e.g. `sqlite3`)
    """

    def filterfunc(path: Path | str, names: list[str]) -> set[str]:
        filtered_files = {
            (root / f).resolve()
            for f in REMOVED_FILES + UNVENDORED_FILES + NOT_ZIPPED_FILES
        }

        path = Path(path).resolve()

        if path.name == "__pycache__":
            return set(names)

        _names = []
        for name in names:

            fullpath = path / name

            if fullpath.name == "__pycache__" or fullpath in filtered_files:
                if verbose:
                    print(f"Skipping {fullpath}")

                _names.append(name)

        return set(_names)

    return filterfunc


def create_zipfile(
    libdir: Path | str,
    output: Path | str = "python",
    pycompile: bool = False,
    filterfunc: Callable[[str, list[str]], set[str]] | None = None,
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
    libdir
        Path to the directory containing the Python standard library.

    output
        Path to the output zip file. Defaults to python.zip.

    pycompile
        Whether to compile the .py files into .pyc, by default False

    filterfunc
        A function that filters the files to be included in the zip file.
        This function will be passed to {ref}`shutil.copytree` 's ignore argument.
        By default, Pyodide's default filter function is used.

    Returns
    -------
    BytesIO
        A BytesIO object containing the zip file.
    """

    if pycompile:
        raise NotImplementedError(
            "TODO: implement after https://github.com/pyodide/pyodide/pull/3253 is merged"
        )

    libdir = Path(libdir)
    output = Path(output)
    output = output.with_name(output.name.rstrip(".zip"))

    if filterfunc is None:
        filterfunc = default_filterfunc(libdir)

    with TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        shutil.copytree(libdir, temp_dir, ignore=filterfunc, dirs_exist_ok=True)

        shutil.make_archive(str(output), "zip", temp_dir)
