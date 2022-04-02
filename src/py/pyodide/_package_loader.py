import re
import shutil
import sysconfig
import tarfile
from importlib.machinery import EXTENSION_SUFFIXES
from pathlib import Path
from site import getsitepackages
from tempfile import NamedTemporaryFile
from typing import IO, Iterable, Literal
from zipfile import ZipFile

from ._core import IN_BROWSER, JsProxy, to_js

SITE_PACKAGES = Path(getsitepackages()[0])
STD_LIB = Path(sysconfig.get_path("stdlib"))
TARGETS = {"site": SITE_PACKAGES, "lib": STD_LIB}
ZIP_TYPES = {".whl", ".zip"}
TAR_TYPES = {".tar", ".gz", ".bz", ".gz", ".tgz", ".bz2", ".tbz2"}
EXTENSION_TAGS = [suffix.removesuffix(".so") for suffix in EXTENSION_SUFFIXES]
# See PEP 3149. I think the situation has since been updated since PEP 3149 does
# not talk about platform triples. But I could not find any newer pep discussing
# shared library names.
#
# There are other interpreters but it's better to have false negatives than
# false positives.
PLATFORM_TAG_REGEX = re.compile(
    r"\.(cpython|pypy|jython)-[0-9]{2,}[a-z]*(-[a-z0-9_-]*)?"
)


def make_whlfile(*args, owner=None, group=None, **kwargs):
    return shutil._make_zipfile(*args, **kwargs)  # type: ignore[attr-defined]


if IN_BROWSER:
    shutil.register_archive_format("whl", make_whlfile, description="Wheel file")
    shutil.register_unpack_format(
        "whl", [".whl", ".wheel"], shutil._unpack_zipfile, description="Wheel file"  # type: ignore[attr-defined]
    )


def get_format(format: str) -> str:
    for (fmt, extensions, _) in shutil.get_unpack_formats():
        if format == fmt:
            return fmt
        if format in extensions:
            return fmt
        if "." + format in extensions:
            return fmt
    raise ValueError(f"Unrecognized format {format}")


def unpack_buffer(
    buffer: JsProxy,
    *,
    filename: str = "",
    format: str | None = None,
    target: Literal["site", "lib"] | None = None,
    extract_dir: str | None = None,
    calculate_dynlibs: bool = False,
) -> JsProxy | None:
    """Used to install a package either into sitepackages or into the standard
    library.

    This is a helper method called from ``loadPackage``.

    Parameters
    ----------
    buffer
        A Javascript ``Uint8Array`` with the binary data for the archive.

    filename
        The name of the file we are extracting. We only care about it to figure
        out whether the buffer represents a tar file or a zip file. Ignored if
        format argument is present.

    format
        Controls the format that we assume the archive has. Overrides the file
        extension of filename. In particular we decide the file format as
        follows:

        1. If format is present, we use that.
        2. If file name is present, it should have an extension, like a.zip,
           a.tar, etc. Then we use that.
        3. If neither is present or the file name has no extension, we throw an
           error.


    extract_dir
        Controls which directory the file is unpacked into. Default is the
        working directory. Mutually exclusive with target.

    target
        Controls which directory the file is unpacked into. Either "site" which
        unpacked the file into the sitepackages directory or "lib" which
        unpacked the file into the standard library. Mutually exclusive with
        extract_dir.

    calculate_dynlibs
        If true, will return a Javascript Array of paths to dynamic libraries
        ('.so' files) that were in the archive. We need to precompile these Wasm
        binaries in `load-pyodide.js`. These paths point to the unpacked
        locations of the .so files.

    Returns
    -------
        If calculate_dynlibs is True, a Javascript Array of dynamic libraries.
        Otherwise, return None.

    """
    if format:
        format = get_format(format)
    if target and extract_dir:
        raise ValueError("Cannot provide both 'target' and 'extract_dir'")
    if not filename and format is None:
        raise ValueError("At least one of filename and format must be provided")
    if target:
        extract_path = TARGETS[target]
    elif extract_dir:
        extract_path = Path(extract_dir)
    else:
        extract_path = Path(".")
    with NamedTemporaryFile(suffix=filename) as f:
        buffer._into_file(f)
        shutil.unpack_archive(f.name, extract_path, format)
        if calculate_dynlibs:
            return to_js(get_dynlibs(f, extract_path))
        else:
            return None


def should_load_dynlib(path: str):
    suffixes = Path(path).suffixes
    if not suffixes:
        return False
    if suffixes[-1] != ".so":
        return False
    if len(suffixes) == 1:
        return True
    tag = suffixes[-2]
    if tag in EXTENSION_TAGS:
        return True
    # Okay probably it's not compatible now. But it might be an unrelated .so
    # file with a name with an extra dot: `some.name.so` vs
    # `some.cpython-39-x86_64-linux-gnu.so` Let's make a best effort here to
    # check.
    return not PLATFORM_TAG_REGEX.match(tag)


def get_dynlibs(archive: IO[bytes], target_dir: Path) -> list[str]:
    """List out the paths to .so files in a zip or tar archive.

    Parameters
    ----------
    archive
        A binary representation of either a zip or a tar archive. We use the `.name`
        field to determine which file type.

    target_dir
        The directory the archive is unpacked into. Paths will be adjusted to point
        inside this directory.

    Returns
    -------
        The list of paths to dynamic libraries ('.so' files) that were in the archive,
        but adjusted to point to their unpacked locations.
    """
    suffix = Path(archive.name).suffix
    dynlib_paths_iter: Iterable[str]
    if suffix in ZIP_TYPES:
        dynlib_paths_iter = ZipFile(archive).namelist()
    elif suffix in TAR_TYPES:
        dynlib_paths_iter = (tinfo.name for tinfo in tarfile.open(archive.name))
    else:
        raise ValueError(f"Unexpected suffix {suffix}")

    return [
        str((target_dir / path).resolve())
        for path in dynlib_paths_iter
        if should_load_dynlib(path)
    ]
