from ._core import to_js
from tempfile import NamedTemporaryFile
import shutil

from site import getsitepackages
import pathlib

SITE_PACKAGES = pathlib.Path(getsitepackages()[0])


def unpack_buffer(filename, buffer):
    with NamedTemporaryFile(suffix=filename) as f:
        buffer._into_file(f)
        shutil.unpack_archive(f.name, SITE_PACKAGES)


async def get_dynlibs(name):
    return to_js([str(x) for x in (SITE_PACKAGES / name).glob("**/*.so")])
