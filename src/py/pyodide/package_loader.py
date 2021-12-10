from .http import pyfetch
from ._core import to_js

from site import getsitepackages
import pathlib

SITE_PACKAGES = pathlib.Path(getsitepackages()[0])


async def load_package(url, name):
    resp = await pyfetch(url)
    await resp.unpack_archive(extract_dir=SITE_PACKAGES)
    return to_js(list((SITE_PACKAGES / name).glob("**/*.so")))
