import tarfile
from ._core import to_js
from tempfile import NamedTemporaryFile
import shutil

from site import getsitepackages
from zipfile import ZipFile
import pathlib

SITE_PACKAGES = pathlib.Path(getsitepackages()[0])


def unpack_buffer(filename, buffer):
    with NamedTemporaryFile(suffix=filename) as f:
        buffer._into_file(f)
        shutil.unpack_archive(f.name, SITE_PACKAGES)
        return get_dynlibs(f)


def get_dynlibs(f):
    dynlibs = []
    suffix = pathlib.Path(f.name).suffix
    if suffix in [".whl", ".zip"]:
        for name in ZipFile(f).namelist():
            if name.endswith(".so"):
                dynlibs.append(str((SITE_PACKAGES / name).resolve()))
    elif suffix in [".tar", ".gz", ".bz", ".gz", ".tgz", ".bz2", ".tbz2"]:
        for tinfo in tarfile.open(f.name):
            if tinfo.name.endswith(".so"):
                dynlibs.append(str((SITE_PACKAGES / tinfo.name).resolve()))
    else:
        raise ValueError(f"Unexpected suffix {suffix}")
    return to_js(dynlibs)
