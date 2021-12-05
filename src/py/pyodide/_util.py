from tempfile import NamedTemporaryFile
import shutil


def unpack_buffer_archive(buf, format, extract_dir="."):
    with NamedTemporaryFile() as f:
        buf._into_file(f)
        shutil.unpack_archive(f.name, extract_dir, format)
