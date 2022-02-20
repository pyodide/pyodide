#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import urllib.request
import urllib.error
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional, Literal
import warnings

PACKAGES_ROOT = Path(__file__).parents[2] / "packages"


class MkpkgFailedException(Exception):
    pass


SDIST_EXTENSIONS = tuple(
    extension
    for (name, extensions, description) in shutil.get_unpack_formats()
    for extension in extensions
)


def _find_sdist(pypi_metadata: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Get sdist file path from the metadata"""
    # The first one we can use. Usually a .tar.gz
    for entry in pypi_metadata["urls"]:
        if entry["packagetype"] == "sdist" and entry["filename"].endswith(
            SDIST_EXTENSIONS
        ):
            return entry
    return None


def _find_wheel(pypi_metadata: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Get wheel file path from the metadata"""
    for entry in pypi_metadata["urls"]:
        if entry["packagetype"] == "bdist_wheel" and entry["filename"].endswith(
            "py3-none-any.whl"
        ):
            return entry
    return None


def _find_dist(
    pypi_metadata: dict[str, Any], source_types=list[Literal["wheel", "sdist"]]
) -> dict[str, Any]:
    """Find a wheel or sdist, as appropriate.

    source_types controls which types (wheel and/or sdist) are accepted and also
    the priority order.
    E.g., ["wheel", "sdist"] means accept either wheel or sdist but prefer wheel.
    ["sdist", "wheel"] means accept either wheel or sdist but prefer sdist.
    """
    result = None
    for source in source_types:
        if source == "wheel":
            result = _find_wheel(pypi_metadata)
        if source == "sdist":
            result = _find_sdist(pypi_metadata)
        if result:
            return result

    types_str = " or ".join(source_types)
    name = pypi_metadata["info"].get("name")
    url = pypi_metadata["info"].get("package_url")
    raise MkpkgFailedException(f"No {types_str} found for package {name} ({url})")


def _get_metadata(package: str, version: Optional[str] = None) -> dict:
    """Download metadata for a package from PyPI"""
    version = ("/" + version) if version is not None else ""
    url = f"https://pypi.org/pypi/{package}{version}/json"

    try:
        with urllib.request.urlopen(url) as fd:
            pypi_metadata = json.load(fd)
    except urllib.error.HTTPError as e:
        raise MkpkgFailedException(
            f"Failed to load metadata for {package}{version} from "
            f"https://pypi.org/pypi/{package}{version}/json: {e}"
        )

    return pypi_metadata


def _import_ruamel_yaml():
    """Import ruamel.yaml with a better error message is not installed."""
    try:
        from ruamel.yaml import YAML
    except ImportError as err:
        raise ImportError(
            "No module named 'ruamel'. "
            "It can be installed with pip install ruamel.yaml"
        ) from err
    return YAML


def run_prettier(meta_path):
    subprocess.run(["npx", "prettier", "-w", meta_path])


def make_package(
    package: str,
    version: Optional[str] = None,
    source_fmt: Optional[Literal["wheel", "sdist"]] = None,
):
    """
    Creates a template that will work for most pure Python packages,
    but will have to be edited for more complex things.
    """
    print(f"Creating meta.yaml package for {package}")
    YAML = _import_ruamel_yaml()

    yaml = YAML()

    pypi_metadata = _get_metadata(package, version)

    if source_fmt:
        sources = [source_fmt]
    else:
        # Prefer wheel unless sdist is specifically requested.
        sources = ["wheel", "sdist"]
    dist_metadata = _find_dist(pypi_metadata, sources)

    url = dist_metadata["url"]
    sha256 = dist_metadata["digests"]["sha256"]
    version = pypi_metadata["info"]["version"]

    homepage = pypi_metadata["info"]["home_page"]
    summary = pypi_metadata["info"]["summary"]
    license = pypi_metadata["info"]["license"]
    pypi = "https://pypi.org/project/" + package

    yaml_content = {
        "package": {"name": package, "version": version},
        "source": {"url": url, "sha256": sha256},
        "test": {"imports": [package]},
        "about": {
            "home": homepage,
            "PyPI": pypi,
            "summary": summary,
            "license": license,
        },
    }

    if not (PACKAGES_ROOT / package).is_dir():
        os.makedirs(PACKAGES_ROOT / package)
    meta_path = PACKAGES_ROOT / package / "meta.yaml"
    with open(meta_path, "w") as fd:
        yaml.dump(yaml_content, fd)
    run_prettier(meta_path)
    success(f"Output written to {meta_path}")


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


def update_package(
    package: str,
    update_patched: bool = True,
    source_fmt: Optional[Literal["wheel", "sdist"]] = None,
):

    YAML = _import_ruamel_yaml()
    yaml = YAML()

    meta_path = PACKAGES_ROOT / package / "meta.yaml"
    if not meta_path.exists():
        print(f"{meta_path} does not exist")
        sys.exit(0)
    with open(meta_path, "rb") as fd:
        yaml_content = yaml.load(fd)

    if "url" not in yaml_content["source"]:
        print(f"Skipping: {package} is a local package!")
        sys.exit(0)

    build_info = yaml_content.get("build", {})
    if build_info.get("library", False) or build_info.get("sharedlibrary", False):
        print(f"Skipping: {package} is a library!")
        sys.exit(0)

    if yaml_content["source"]["url"].endswith("whl"):
        old_fmt = "wheel"
    else:
        old_fmt = "sdist"

    pypi_metadata = _get_metadata(package)
    pypi_ver = pypi_metadata["info"]["version"]
    local_ver = yaml_content["package"]["version"]
    already_up_to_date = pypi_ver <= local_ver and (
        source_fmt is None or source_fmt == old_fmt
    )
    if already_up_to_date:
        print(f"{package} already up to date. Local: {local_ver} PyPI: {pypi_ver}")
        sys.exit(0)

    print(f"{package} is out of date: {local_ver} <= {pypi_ver}.")

    if "patches" in yaml_content["source"]:
        if update_patched:
            warn(
                f"Pyodide applies patches to {package}. Update the "
                "patches (if needed) to avoid build failing."
            )
        else:
            abort(f"Pyodide applies patches to {package}. Skipping update.")

    if source_fmt:
        # require the type requested
        sources = [source_fmt]
    elif old_fmt == "wheel":
        # prefer wheel to sdist
        sources = ["wheel", "sdist"]
    else:
        # prefer sdist to wheel
        sources = ["sdist", "wheel"]

    dist_metadata = _find_dist(pypi_metadata, sources)

    yaml_content["source"]["url"] = dist_metadata["url"]
    yaml_content["source"].pop("md5", None)
    yaml_content["source"]["sha256"] = dist_metadata["digests"]["sha256"]
    yaml_content["package"]["version"] = pypi_metadata["info"]["version"]
    with open(meta_path, "wb") as fd:
        yaml.dump(yaml_content, fd)
    run_prettier(meta_path)
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
        "--source-format",
        help="Which source format is prefered. Options are wheel or sdist. "
        "If none is provided, then either a wheel or an sdist will be used. "
        "When updating a package, the type will be kept the same if possible.",
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
            update_package(package, update_patched=True, source_fmt=args.source_format)
            return
        if args.update_if_not_patched:
            update_package(package, update_patched=False, source_fmt=args.source_format)
            return
        make_package(package, args.version, source_fmt=args.source_format)
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
