import shutil
import subprocess
from pathlib import Path

VERSION = "3380500"
HASH = "6f515a7782bfb5414702721fc78ada5bf388f4bf8b3e3c2ec269df33a2e372859f682d028c30084e89847705c7050ea80790d51fbcc4decea8fbb0a35b89c0b3"


def needed(settings):
    # This library will be built manually using embuilder
    return False


def get(ports, settings, shared):
    ports.fetch_project(
        "sqlite",
        "https://sqlite.org/2022/sqlite-autoconf-" + VERSION + ".tar.gz",
        "sqlite-autoconf-" + VERSION,
        sha512hash=HASH,
    )

    def create(final):
        ports.clear_project_build("sqlite")

        source_path = Path(ports.get_dir(), "sqlite", "sqlite-autoconf-" + VERSION)
        dest_path = Path(ports.get_build_dir(), "sqlite")
        shared.try_delete(dest_path)
        dest_path.mkdir(parents=True)
        shutil.rmtree(dest_path, ignore_errors=True)
        shutil.copytree(source_path, dest_path)

        # build
        # sqlite fails to detect that popen is not available. We have to set it
        # as a CPPFLAG

        subprocess.run(
            f"""
          cd {dest_path}
          emconfigure ./configure CFLAGS="-fPIC" CPPFLAGS="-DSQLITE_OMIT_POPEN" &&
          emmake make -j ${{PYODIDE_JOBS:-3}}
          """,
            shell=True,
            capture_output=True,
        )

        ports.install_headers(source_path)
        for lib in (dest_path / ".libs").glob("*"):
            shutil.copy(lib, Path(final).parent)

    return [shared.Cache.get_lib("libsqlite3.a", create, what="port")]


def clear(ports, settings, shared):
    shared.Cache.erase_lib("libsqlite3.a")


def process_args(ports):
    return []


def show():
    return "sqlite"
