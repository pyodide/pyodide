import tarfile
from ._core import to_js
from tempfile import NamedTemporaryFile
import shutil

from site import getsitepackages
from zipfile import ZipFile
import pathlib
import sysconfig

SITE_PACKAGES = pathlib.Path(getsitepackages()[0])
STD_LIB = pathlib.Path(sysconfig.get_path("stdlib"))  # type: ignore

TARGETS = {"site": SITE_PACKAGES, "lib": STD_LIB}


def unpack_buffer(filename, buffer, target="site"):
    print("unpack", filename, target)
    target_dir = TARGETS[target]
    with NamedTemporaryFile(suffix=filename) as f:
        buffer._into_file(f)
        shutil.unpack_archive(f.name, target_dir)
        return get_dynlibs(f, target_dir)


ZIP_TYPES = {".whl", ".zip"}
TAR_TYPES = {".tar", ".gz", ".bz", ".gz", ".tgz", ".bz2", ".tbz2"}


def get_dynlibs(f, target_dir):
    dynlibs = []
    suffix = pathlib.Path(f.name).suffix
    if suffix in ZIP_TYPES:
        for name in ZipFile(f).namelist():
            if name.endswith(".so"):
                dynlibs.append(str((target_dir / name).resolve()))
    elif suffix in TAR_TYPES:
        for tinfo in tarfile.open(f.name):
            if tinfo.name.endswith(".so"):
                dynlibs.append(str((target_dir / tinfo.name).resolve()))
    else:
        raise ValueError(f"Unexpected suffix {suffix}")
    return to_js(dynlibs)
