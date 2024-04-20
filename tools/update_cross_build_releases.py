import argparse
import hashlib
import json
from pathlib import Path

import requests

from pyodide_build.xbuildenv_releases import (
    CrossBuildEnvMetaSpec,
    CrossBuildEnvReleaseSpec,
)

METADATA_FILE = Path(__file__).parents[1] / "pyodide-cross-build-environments.json"

BASE_URL = "https://github.com/pyodide/pyodide/releases/download/{version}/xbuildenv-{version}.tar.bz2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Update cross-build environments files")
    parser.add_argument("version", help="version of the cross-build environment")

    return parser.parse_args()


def get_archive(url: str) -> bytes:
    resp = requests.get(url)
    resp.raise_for_status()

    return resp.content


def add_version(raw_metadata: str, version: str, url: str, digest: str) -> str:
    metadata = CrossBuildEnvMetaSpec.parse_raw(raw_metadata)
    new_release = CrossBuildEnvReleaseSpec(
        version=version,
        url=url,
        sha256=digest,
        python_version="FIXME",
        emscripten_version="FIXME",
        min_pyodide_build_version="FIXME",
        max_pyodide_build_version="FIXME",
    )

    metadata.releases[version] = new_release

    # Sort releases in reverse order
    metadata.releases = dict(sorted(metadata.releases.items(), reverse=True))

    dictionary = metadata.dict()
    return json.dumps(dictionary, indent=2)


def main():
    args = parse_args()

    version = args.version
    full_url = BASE_URL.format(version=version)

    content = get_archive(full_url)
    digest = hashlib.sha256(content).hexdigest()

    metadata = METADATA_FILE.read_text()
    new_metadata = add_version(metadata, version, full_url, digest)

    METADATA_FILE.write_text(new_metadata)


if __name__ == "__main__":
    main()
