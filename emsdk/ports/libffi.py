import shutil
import subprocess
from pathlib import Path

VERSION = "2022-06-23"
HASH = "99b4cf5c7e2d8ef8cec64dd9626202c4d6b82440a379344cb6dc6e3f0607214c8d898c781d238a68ba58d235a9a01bc23ecc40e75a9263570748ec319962235d"


def needed(settings):
    # This library will be built manually using embuilder
    return False


def get(ports, settings, shared):
    ports.fetch_project(
        "libffi",
        f"https://github.com/hoodmane/libffi-emscripten/archive/refs/tags/{VERSION}.tar.gz",
        f"libffi-emscripten{VERSION}",
        sha512hash=HASH,
    )

    def create(final):
        ports.clear_project_build("libffi")

        source_path = Path(ports.get_dir(), "libffi", f"libffi-emscripten-{VERSION}")
        dest_path = Path(ports.get_build_dir(), "libffi")
        shared.try_delete(dest_path)
        dest_path.mkdir(parents=True)
        shutil.rmtree(dest_path, ignore_errors=True)
        shutil.copytree(source_path, dest_path)

        subprocess.run(
            f"""
            cd {dest_path}
            ./build.sh
            """,
            shell=True,
            capture_output=True,
        )

        ports.install_headers(dest_path / "target" / "include")
        shutil.copy(dest_path / "target" / "lib" / "libffi.a", final)

    return [shared.Cache.get_lib("libffi.a", create, what="port")]


def clear(ports, settings, shared):
    shared.Cache.erase_lib("libffi.a")


def process_args(ports):
    return []


def show():
    return "libffi"
