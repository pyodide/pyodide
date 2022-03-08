import shutil
from tempfile import NamedTemporaryFile

from ._core import IN_BROWSER


def make_whlfile(*args, owner=None, group=None, **kwargs):
    return shutil._make_zipfile(*args, **kwargs)  # type: ignore[attr-defined]


if IN_BROWSER:
    shutil.register_archive_format("whl", make_whlfile, description="Wheel file")
    shutil.register_unpack_format(
        "whl", [".whl", ".wheel"], shutil._unpack_zipfile, description="Wheel file"  # type: ignore[attr-defined]
    )


def get_format(format):
    for (fmt, extensions, _) in shutil.get_unpack_formats():
        if format == fmt:
            return fmt
        if format in extensions:
            return fmt
        if "." + format in extensions:
            return fmt
    raise ValueError(f"Unrecognized format {format}")


def unpack_buffer_archive(buf, *, filename="", format=None, extract_dir="."):
    if format:
        format = get_format(format)
    with NamedTemporaryFile(suffix=filename) as f:
        buf._into_file(f)
        shutil.unpack_archive(f.name, extract_dir, format)
