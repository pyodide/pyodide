import base64
import binascii
import re
import shutil
import sysconfig
import tarfile
from collections.abc import Iterable
from importlib.machinery import EXTENSION_SUFFIXES
from importlib.metadata import Distribution
from importlib.metadata import distributions as importlib_distributions
from pathlib import Path
from site import getsitepackages
from tempfile import NamedTemporaryFile
from typing import IO, Any, Literal
from zipfile import ZipFile

try:
    from pyodide_js import loadedPackages
except ImportError:
    loadedPackages = None

from ._core import IN_BROWSER, JsProxy, to_js

SITE_PACKAGES = Path(getsitepackages()[0])
STD_LIB = Path(sysconfig.get_path("stdlib"))
TARGETS = {"site": SITE_PACKAGES, "lib": STD_LIB, "dynlib": Path("/usr/lib")}
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


def parse_wheel_name(filename: str) -> tuple[str, str, str, str, str]:
    tokens = filename.split("-")
    # TODO: support optional build tags in the filename (cf PEP 427)
    if len(tokens) < 5:
        raise ValueError(f"{filename} is not a valid wheel file name.")
    version, python_tag, abi_tag, platform = tokens[-4:]
    name = "-".join(tokens[:-4])
    return name, version, python_tag, abi_tag, platform


# Vendored from packaging
_canonicalize_regex = re.compile(r"[-_.]+")


def canonicalize_name(name: str) -> str:
    # This is taken from PEP 503.
    return _canonicalize_regex.sub("-", name).lower()


# Vendored from pip
class UnsupportedWheel(Exception):
    """Unsupported wheel."""


def wheel_dist_info_dir(source: ZipFile, name: str) -> str:
    """Returns the name of the contained .dist-info directory.

    Raises UnsupportedWheel if not found, >1 found, or it doesn't match the
    provided name.
    """
    # Zip file path separators must be /
    subdirs = {p.split("/", 1)[0] for p in source.namelist()}

    info_dirs = [s for s in subdirs if s.endswith(".dist-info")]

    if not info_dirs:
        raise UnsupportedWheel(f".dist-info directory not found in wheel {name!r}")

    if len(info_dirs) > 1:
        raise UnsupportedWheel(
            "multiple .dist-info directories found in wheel {!r}: {}".format(
                name, ", ".join(info_dirs)
            )
        )

    info_dir = info_dirs[0]

    info_dir_name = canonicalize_name(info_dir)
    canonical_name = canonicalize_name(name)
    if not info_dir_name.startswith(canonical_name):
        raise UnsupportedWheel(
            ".dist-info directory {!r} does not start with {!r}".format(
                info_dir, canonical_name
            )
        )

    return info_dir


def make_whlfile(
    *args: Any, owner: int | None = None, group: int | None = None, **kwargs: Any
) -> str:
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
    target: Literal["site", "lib", "dynlib"] | None = None,
    extract_dir: str | None = None,
    calculate_dynlibs: bool = False,
    installer: str | None = None,
    source: str | None = None,
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
    filename = filename.rpartition("/")[-1]
    with NamedTemporaryFile(suffix=filename) as f:
        buffer._into_file(f)
        shutil.unpack_archive(f.name, extract_path, format)
        suffix = Path(filename).suffix
        if suffix == ".whl":
            set_wheel_installer(filename, f, extract_path, installer, source)
        if calculate_dynlibs:
            suffix = Path(f.name).suffix
            return to_js(get_dynlibs(f, suffix, extract_path))
        else:
            return None


def should_load_dynlib(path: str) -> bool:
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


def set_wheel_installer(
    filename: str,
    archive: IO[bytes],
    target_dir: Path,
    installer: str | None,
    source: str | None,
) -> None:
    """Record the installer and source of a wheel into the `dist-info`
    directory.

    We put the installer into an INSTALLER file according to the packaging spec:
    packaging.python.org/en/latest/specifications/recording-installed-packages/#the-dist-info-directory

    We put the source into PYODIDE_SORUCE.

    The packaging spec allows us to make custom files. It also allows wheels to
    include custom files in their .dist-info directory. The spec has no attempt
    to coordinate these so that installers don't trample files that wheels
    include. We make a best effort with our PYODIDE prefix.

    Parameters
    ----------
    filename
        The file name of the wheel.

    archive
        A binary representation of a wheel archive

    target_dir
        The directory the wheel is being installed into. Probably site-packages.

    installer
        The name of the installer. Currently either `pyodide.unpackArchive`,
        `pyodide.loadPackage` or `micropip`.

    source
        Where did the package come from? Either a url, `pyodide`, or `PyPI`.
    """
    z = ZipFile(archive)
    wheel_name = parse_wheel_name(filename)[0]
    dist_info_name = wheel_dist_info_dir(z, wheel_name)
    dist_info = target_dir / dist_info_name
    if installer:
        (dist_info / "INSTALLER").write_text(installer)
    if source:
        (dist_info / "PYODIDE_SOURCE").write_text(source)


def get_dynlibs(archive: IO[bytes], suffix: str, target_dir: Path) -> list[str]:
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


def get_dist_source(dist: Distribution) -> str:
    """Get a description of the source of a package.

    This is used in loadPackage to explain where the package came from. Purely
    for informative purposes.
    """
    source = dist.read_text("PYODIDE_SOURCE")
    if source == "pyodide":
        return "default channel"
    if source:
        return source
    direct_url = dist.read_text("direct_url.json")
    if direct_url:
        import json

        return json.loads(direct_url)["url"]
    installer = dist.read_text("INSTALLER")
    if installer:
        installer = installer.strip()
        return f"{installer} (index unknown)"
    return "Unknown"


def init_loaded_packages() -> None:
    """Initialize pyodide.loadedPackages with the packages that are already
    present.

    This ensures that `pyodide.loadPackage` knows that they are around and
    doesn't install over them.
    """
    for dist in importlib_distributions():
        setattr(loadedPackages, dist.name, get_dist_source(dist))


def sub_resource_hash(sha_256: str) -> str:
    """Calculates the sub resource integrity hash given a SHA-256

    Parameters
    ----------
    sha_256
        A hexdigest of the SHA-256 sum.

    Returns
    -------
        The sub resource integrity hash corresponding to the sum.

    >>> sha_256 = 'c0dc86efda0060d4084098a90ec92b3d4aa89d7f7e0fba5424561d21451e1758'
    >>> sub_resource_hash(sha_256)
    'sha256-wNyG79oAYNQIQJipDskrPUqonX9+D7pUJFYdIUUeF1g='
    """
    binary_digest = binascii.unhexlify(sha_256)
    return "sha256-" + base64.b64encode(binary_digest).decode()
