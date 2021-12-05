from tempfile import NamedTemporaryFile
import shutil


def get_format(format):
    for (fmt, extensions, _) in shutil.get_unpack_formats():
        if format == fmt:
            return fmt
        if format in extensions:
            return fmt
        if "." + format in extensions:
            return fmt
    raise ValueError(f"Unrecognized format {format}")


def unpack_buffer_archive(buf, format, extract_dir="."):
    with NamedTemporaryFile() as f:
        buf._into_file(f)
        shutil.unpack_archive(f.name, extract_dir, get_format(format))
