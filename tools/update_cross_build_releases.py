import argparse
import hashlib
import json
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import requests
from packaging.version import Version

from pyodide_build.xbuildenv_releases import (
    CrossBuildEnvMetaSpec,
    CrossBuildEnvReleaseSpec,
)

# This file must be called from the root of the repository for the path to work
METADATA_FILE = Path(__file__).parents[1] / "pyodide-cross-build-environments.json"

BASE_URL = "https://github.com/pyodide/pyodide/releases/download/{version}/xbuildenv-{version}.tar.bz2"

# Pyodide build version that is compatible with the latest cross-build environment
# Note for maintainers: update this value when there is a breaking changes in the cross-build environment
MIN_COMPATIBLE_PYODIDE_BUILD_VERSION = "0.26.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Update cross-build environments files")
    parser.add_argument("version", help="version of the cross-build environment")

    return parser.parse_args()


def get_archive(url: str) -> bytes:
    resp = requests.get(url)
    resp.raise_for_status()

    return resp.content


def parse_env_var(content: str, var_name: str) -> str:
    # A very dummy parser for env vars.
    for line in content.splitlines():
        if line.startswith(f"export {var_name}"):
            return line.split("=")[1].strip()

    return ""


@contextmanager
def extract_archive(archive: bytes) -> Generator[Path]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        archive_path = tmp_dir_path / "xbuildenv.tar.bz2"
        archive_path.write_bytes(archive)

        # Extract the archive
        shutil.unpack_archive(str(archive_path), extract_dir=tmp_dir)

        yield tmp_dir_path


def add_version(
    raw_metadata: str,
    version: str,
    url: str,
    digest: str,
    python_version: str | None = None,
    emscripten_version: str | None = None,
    min_pyodide_build_version: str | None = None,
    max_pyodide_build_version: str | None = None,
) -> str:
    metadata = CrossBuildEnvMetaSpec.parse_raw(raw_metadata)
    new_release = CrossBuildEnvReleaseSpec(
        version=version,
        url=url,
        sha256=digest,
        python_version=python_version or "FIXME",
        emscripten_version=emscripten_version or "FIXME",
        min_pyodide_build_version=min_pyodide_build_version or "FIXME",
        # Max version is optional, and maintainers should update it when needed.
        max_pyodide_build_version=max_pyodide_build_version or None,
    )

    metadata.releases[version] = new_release

    # Sort releases in reverse order
    metadata.releases = dict(
        sorted(metadata.releases.items(), reverse=True, key=lambda x: Version(x[0]))
    )
    dictionary = metadata.dict(exclude_none=True)
    return json.dumps(dictionary, indent=2)


def main():
    args = parse_args()

    version = args.version
    full_url = BASE_URL.format(version=version)

    content = get_archive(full_url)
    digest = hashlib.sha256(content).hexdigest()

    with extract_archive(content) as extracted:
        makefile_path = extracted / "xbuildenv" / "pyodide-root" / "Makefile.envs"
        makefile_content = makefile_path.read_text()
        python_version = parse_env_var(makefile_content, "PYVERSION")
        emscripten_version = parse_env_var(
            makefile_content, "PYODIDE_EMSCRIPTEN_VERSION"
        )

    metadata = METADATA_FILE.read_text()
    new_metadata = add_version(
        metadata,
        version,
        full_url,
        digest,
        python_version=python_version,
        emscripten_version=emscripten_version,
        min_pyodide_build_version=MIN_COMPATIBLE_PYODIDE_BUILD_VERSION,
    )

    METADATA_FILE.write_text(new_metadata + "\n")


if __name__ == "__main__":
    main()
