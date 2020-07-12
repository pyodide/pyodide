#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import urllib.request
import sys
from pathlib import Path

PACKAGES_ROOT = Path(__file__).parent.parent / "packages"


def _extract_sdist(pypi_metadata):
    sdist_extensions = tuple(
        extension
        for (name, extensions, description) in shutil.get_unpack_formats()
        for extension in extensions
    )

    # The first one we can use. Usually a .tar.gz
    for entry in pypi_metadata["urls"]:
        if entry["filename"].endswith(sdist_extensions):
            return entry

    raise Exception(
        "No sdist URL found for package %s (%s)"
        % (pypi_metadata["info"].get("name"), pypi_metadata["info"].get("package_url"),)
    )


def _get_metadata(package):
    url = f"https://pypi.org/pypi/{package}/json"

    with urllib.request.urlopen(url) as fd:
        pypi_metadata = json.load(fd)

    for entry in json_content["urls"]:
        if entry["filename"].endswith(sdist_extensions_tuple):
            return entry

    raise Exception(
        "No sdist URL found for package %s (%s)"
        % (json_content["info"].get("name"), json_content["info"].get("package_url"),)
    )


def make_package(package, version=None):
    """
    Creates a template that will work for most pure Python packages,
    but will have to be edited for more complex things.
    """
    import yaml

    version = ("/" + version) if version is not None else ""
    url = f"https://pypi.org/pypi/{package}{version}/json"

    with urllib.request.urlopen(url) as fd:
        json_content = json.load(fd)

    entry = get_sdist_url_entry(json_content)
    download_url = entry["url"]
    sha256 = entry["digests"]["sha256"]
    version = json_content["info"]["version"]

    yaml_content = {
        "package": {"name": package, "version": version},
        "source": {"url": download_url, "sha256": sha256},
        "test": {"imports": [package]},
    }

    if not (PACKAGES_ROOT / package).is_dir():
        os.makedirs(PACKAGES_ROOT / package)
    with open(PACKAGES_ROOT / package / "meta.yaml", "w") as fd:
        yaml.dump(yaml_content, fd, default_flow_style=False)


def update_package(package):
    import yaml

    with open(PACKAGES_ROOT / package / "meta.yaml", "r") as fd:
        yaml_content = yaml.load(fd, Loader=yaml.FullLoader)

    if set(yaml_content.keys()) != set(("package", "source", "test")):
        print(
            "Only pure-python packages can be updated using this script. " "Aborting."
        )
        sys.exit(1)

    sdist_metadata, pypi_metadata = _get_metadata(package)
    pypi_ver = pypi_metadata["info"]["version"]
    local_ver = yaml_content["package"]["version"]
    if pypi_ver <= local_ver:
        print(f"Already up to date. Local: {local_ver} Pypi: {pypi_ver}")
        sys.exit(0)
    print(f"Updating {package} from {local_ver} to {pypi_ver}")

    if "patches" in yaml_content["source"]:
        import warnings

        warnings.warn(
            f"Pyodide applies patches to {package}. Update the "
            "patches (if needed) to avoid build failing."
        )

    yaml_content["source"]["url"] = sdist_metadata["url"]
    yaml_content["source"].pop("md5", None)
    yaml_content["source"]["sha256"] = sdist_metadata["digests"]["sha256"]
    yaml_content["package"]["version"] = pypi_metadata["info"]["version"]
    with open(PACKAGES_ROOT / package / "meta.yaml", "w") as fd:
        yaml.dump(yaml_content, fd, default_flow_style=False)


def make_parser(parser):
    parser.description = """
Make a new pyodide package. Creates a simple template that will work
for most pure Python packages, but will have to be edited for more
complex things.""".strip()
    parser.add_argument("package", type=str, nargs=1, help="The package name on PyPI")
    parser.add_argument("--update", action="store_true", help="update existing package")
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Package version string, "
        "e.g. v1.2.1 (defaults to latest stable release)",
    )
    return parser


def main(args):
    package = args.package[0]
    if args.update:
        return update_package(package)
    return make_package(package, args.version)


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
