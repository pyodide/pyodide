import argparse
import hashlib
import json
import os
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

# v1 is frozen

# METADATA_FILE_V1 = (
#     Path(__file__).parents[1] / "metadata" / "pyodide-cross-build-environments-v1.json"
# )

METADATA_FILE_V2 = (
    Path(__file__).parents[1] / "metadata" / "pyodide-cross-build-environments-v2.json"
)
METADATA_FILE_DEBUG_V2 = (
    Path(__file__).parents[1]
    / "metadata"
    / "pyodide-cross-build-environments-debug-v2.json"
)

BASE_URL = "https://github.com/pyodide/pyodide/releases/download/{version}/xbuildenv-{version}.tar.gz"
DEBUG_BASE_URL = "https://github.com/pyodide/pyodide/releases/download/{version}/xbuildenv-debug-{version}.tar.gz"

# Pyodide build version that is compatible with the latest cross-build environment
# Note for maintainers: update this value when there are breaking changes in the cross-build environment
MIN_COMPATIBLE_PYODIDE_BUILD_VERSION = "0.26.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Update cross-build environments files")
    parser.add_argument("version", help="version of the cross-build environment")

    return parser.parse_args()


def get_archive(url: str) -> bytes | None:
    resp = requests.get(url)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()

    return resp.content


# If you want to test this locally, you can set a short-lived token
# with GITHUB_TOKEN=$(gh auth token --scopes repo) to avoid hitting the rate limit.
def get_published_at(version: str) -> str:
    url = f"https://api.github.com/repos/pyodide/pyodide/releases/tags/{version}"
    headers = {}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()["published_at"]


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
        archive_path = tmp_dir_path / "xbuildenv.tar.gz"
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
    published_at: str | None = None,
    min_pyodide_build_version: str | None = None,
    max_pyodide_build_version: str | None = None,
) -> str:
    metadata = CrossBuildEnvMetaSpec.model_validate_json(raw_metadata)
    new_release = CrossBuildEnvReleaseSpec(
        version=version,
        url=url,
        sha256=digest,
        python_version=python_version or "FIXME",
        emscripten_version=emscripten_version or "FIXME",
        published_at=published_at or "",
        min_pyodide_build_version=min_pyodide_build_version or "FIXME",
        # Max version is optional, and maintainers should update it when needed.
        max_pyodide_build_version=max_pyodide_build_version or None,
    )

    metadata.releases[version] = new_release

    # Sort releases in reverse order
    metadata.releases = dict(
        sorted(metadata.releases.items(), reverse=True, key=lambda x: Version(x[0]))
    )
    dictionary = metadata.model_dump(exclude_none=True)
    return json.dumps(dictionary, indent=2)


def main():
    args = parse_args()

    version = args.version
    full_url = BASE_URL.format(version=version)

    content = get_archive(full_url)
    if content is None:
        raise RuntimeError(f"Release tarball not found: {full_url}")
    digest = hashlib.sha256(content).hexdigest()

    with extract_archive(content) as extracted:
        makefile_path = extracted / "xbuildenv" / "pyodide-root" / "Makefile.envs"
        makefile_content = makefile_path.read_text()
        python_version = parse_env_var(makefile_content, "PYVERSION")
        emscripten_version = parse_env_var(
            makefile_content, "PYODIDE_EMSCRIPTEN_VERSION"
        )

    published_at = get_published_at(version)

    common_args = dict(
        version=version,
        python_version=python_version,
        emscripten_version=emscripten_version,
        published_at=published_at,
        min_pyodide_build_version=MIN_COMPATIBLE_PYODIDE_BUILD_VERSION,
    )

    # v2 extends v1 by adding published_at. v1 is frozen.

    # new_v1 = add_version(METADATA_FILE_V1.read_text(), **common_args)
    # METADATA_FILE_V1.write_text(new_v1 + "\n")

    new_v2 = add_version(
        METADATA_FILE_V2.read_text(), url=full_url, digest=digest, **common_args
    )
    METADATA_FILE_V2.write_text(new_v2 + "\n")

    # Also update the debug metadata if a debug xbuildenv was published for this release.
    debug_url = DEBUG_BASE_URL.format(version=version)
    debug_content = get_archive(debug_url)
    if debug_content is not None:
        # I'm unsure if this sanity check is best placed here, or in the
        # CircleCI config, or if we should not have it at all altogether
        if len(debug_content) <= len(content):
            raise RuntimeError(
                f"The debug xbuildenv ({len(debug_content):,} bytes) is not larger than "
                f"release xbuildenv ({len(content):,} bytes). The debug build "
                f"(PYODIDE_DEBUG=1) should always produce a larger archive"
            )
        debug_digest = hashlib.sha256(debug_content).hexdigest()
        new_debug_v2 = add_version(
            METADATA_FILE_DEBUG_V2.read_text(),
            url=debug_url,
            digest=debug_digest,
            **common_args,
        )
        METADATA_FILE_DEBUG_V2.write_text(new_debug_v2 + "\n")
    else:
        print(f"No debug xbuildenv found for {version}, skipping debug metadata update")


if __name__ == "__main__":
    main()
