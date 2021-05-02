#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import urllib.request
import urllib.error
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import warnings

from .io import parse_package_config

PACKAGES_ROOT = Path(__file__).parent.parent / "packages"


class MkpkgFailedException(Exception):
    pass


def _extract_sdist(pypi_metadata: Dict[str, Any]) -> Dict:
    """Get sdist file path from the meta-data"""
    sdist_extensions = tuple(
        extension
        for (name, extensions, description) in shutil.get_unpack_formats()
        for extension in extensions
    )

    # The first one we can use. Usually a .tar.gz
    for entry in pypi_metadata["urls"]:
        if entry["filename"].endswith(sdist_extensions):
            return entry

    raise MkpkgFailedException(
        "No sdist URL found for package %s (%s)"
        % (
            pypi_metadata["info"].get("name"),
            pypi_metadata["info"].get("package_url"),
        )
    )


def _get_metadata(package: str, version: Optional[str] = None) -> Dict:
    """Download metadata for a package from PyPi"""
    version = ("/" + version) if version is not None else ""
    url = f"https://pypi.org/pypi/{package}{version}/json"

    try:
        with urllib.request.urlopen(url) as fd:
            pypi_metadata = json.load(fd)
    except urllib.error.HTTPError as e:
        raise MkpkgFailedException(
            f"Failed to load metadata for {package}{version} from https://pypi.org/pypi/{package}{version}/json: {e}"
        )

    return pypi_metadata


def make_package(package: str, version: Optional[str] = None):
    """
    Creates a template that will work for most pure Python packages,
    but will have to be edited for more complex things.
    """
    import yaml

    pypi_metadata = _get_metadata(package, version)
    sdist_metadata = _extract_sdist(pypi_metadata)

    url = sdist_metadata["url"]
    sha256 = sdist_metadata["digests"]["sha256"]
    version = pypi_metadata["info"]["version"]

    yaml_content = {
        "package": {"name": package, "version": version},
        "source": {"url": url, "sha256": sha256},
        "test": {"imports": [package]},
    }

    if not (PACKAGES_ROOT / package).is_dir():
        os.makedirs(PACKAGES_ROOT / package)
    with open(PACKAGES_ROOT / package / "meta.yaml", "w") as fd:
        yaml.dump(yaml_content, fd, default_flow_style=False)


class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def abort(msg):
    print(bcolors.FAIL + msg + bcolors.ENDC)
    sys.exit(1)


def warn(msg):
    warnings.warn(bcolors.WARNING + msg + bcolors.ENDC)


def success(msg):
    print(bcolors.OKBLUE + msg + bcolors.ENDC)


def update_package(package: str, update_patched: bool = True):
    from ruamel.yaml import YAML

    yaml = YAML()

    meta_path = PACKAGES_ROOT / package / "meta.yaml"
    yaml_content = parse_package_config(meta_path)

    if "url" not in yaml_content["source"]:
        print(f"Skipping: {package} is a local package!")
        sys.exit(0)

    build_info = yaml_content.get("build", {})
    if build_info.get("library", False) or build_info.get("sharedlibrary", False):
        print(f"Skipping: {package} is a library!")
        sys.exit(0)

    pypi_metadata = _get_metadata(package)
    pypi_ver = pypi_metadata["info"]["version"]
    local_ver = yaml_content["package"]["version"]
    if pypi_ver <= local_ver:
        print(f"{package} already up to date. Local: {local_ver} PyPi: {pypi_ver}")
        sys.exit(0)

    print(f"{package} is out of date: {local_ver} <= {pypi_ver}.")
    if set(yaml_content.keys()).difference(
        ("package", "source", "test", "requirements")
    ):
        abort(
            f"{package}: Only pure python packages can be updated using this script. "
            f"Aborting."
        )

    if "patches" in yaml_content["source"]:
        if update_patched:
            warn(
                f"Pyodide applies patches to {package}. Update the "
                "patches (if needed) to avoid build failing."
            )
        else:
            abort(f"Pyodide applies patches to {package}. Skipping update.")

    sdist_metadata = _extract_sdist(pypi_metadata)

    yaml_content["source"]["url"] = sdist_metadata["url"]
    yaml_content["source"].pop("md5", None)
    yaml_content["source"]["sha256"] = sdist_metadata["digests"]["sha256"]
    yaml_content["package"]["version"] = pypi_metadata["info"]["version"]
    with open(PACKAGES_ROOT / package / "meta.yaml", "w") as fd:
        yaml.dump(yaml_content, fd)
    success(f"Updated {package} from {local_ver} to {pypi_ver}.")


def make_parser(parser):
    parser.description = """
Make a new pyodide package. Creates a simple template that will work
for most pure Python packages, but will have to be edited for more
complex things.""".strip()
    parser.add_argument("package", type=str, nargs=1, help="The package name on PyPI")
    parser.add_argument("--update", action="store_true", help="Update existing package")
    parser.add_argument(
        "--update-if-not-patched",
        action="store_true",
        help="Update existing package if it has no patches",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Package version string, "
        "e.g. v1.2.1 (defaults to latest stable release)",
    )
    return parser


def main(args):
    try:
        package = args.package[0]
        if args.update:
            update_package(package, update_patched=True)
            return
        if args.update_if_not_patched:
            update_package(package, update_patched=False)
            return
        make_package(package, args.version)
    except MkpkgFailedException as e:
        # This produces two types of error messages:
        #
        # When the request to get the pypi json fails, it produces a message like:
        # "Failed to load metadata for libxslt from https://pypi.org/pypi/libxslt/json: HTTP Error 404: Not Found"
        #
        # If there is no sdist it prints an error message like:
        # "No sdist URL found for package swiglpk (https://pypi.org/project/swiglpk/)"
        abort(e.args[0])


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
