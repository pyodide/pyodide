import shutil
import sysconfig
import tarfile
from pathlib import Path
from site import getsitepackages
from tempfile import NamedTemporaryFile
from typing import IO, Iterable, Literal, Optional
from zipfile import ZipFile

from ._core import IN_BROWSER, JsProxy, to_js

SITE_PACKAGES = Path(getsitepackages()[0])
STD_LIB = Path(sysconfig.get_path("stdlib"))
TARGETS = {"site": SITE_PACKAGES, "lib": STD_LIB}
ZIP_TYPES = {".whl", ".zip"}
TAR_TYPES = {".tar", ".gz", ".bz", ".gz", ".tgz", ".bz2", ".tbz2"}


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
    format: str = None,
    target: Literal["site", "lib", None] = None,
    extract_dir: str = None,
    calculate_dynlibs: bool = False,
) -> Optional[JsProxy]:
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
        extension of filename.

    extract_dir
        Controls which directory the file is unpacked into. Default is the
        working directory. Mutually exclusive with target.

    target
        Controls which directory the file is unpacked into. Either "site" which
        unpacked the file into the sitepackages directory or "lib" which
        unpacked the file into the standard library. Mutually exclusive with
        extract_dir.


    Returns
    -------
        A Javascript Array of paths to dynamic libraries ('.so' files) that were
        in the archive. We need to precompile these Wasm binaries in
        `load-pyodide.js`. These paths point to the unpacked locations of the
        .so files.
    """
    if format:
        format = get_format(format)
    if target and extract_dir:
        raise ValueError("Cannot provide both 'target' and 'extract_dir'")
    if not filename and not format:
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
        if path.endswith(".so")
    ]
