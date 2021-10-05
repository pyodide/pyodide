#!/usr/bin/env python

import sys
import pathlib
from typing import Dict, Any

base_dir = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(base_dir / "pyodide-build"))

from pyodide_build.io import parse_package_config

PACKAGES_DIR = base_dir / "packages"
OUTPUT_FILE = "packages-in-pyodide.md"
OUTPUT_PATH = base_dir / "docs" / "usage" / OUTPUT_FILE

TEMPLATE = """
(packages-in-pyodide)=
# Packages built in Pyodide

The list of prebuilt Python packages in the current version of Pyodide.
These packages can be loaded through {{any}}`pyodide.loadPackage` or {{any}}`micropip.install`.
See {{ref}}`loading_packages` for information about loading packages.
Note that in addition to this list, pure Python packages with wheels can be loaded
directly from PyPI with {{any}}`micropip.install`.


| Name  | Version |
| :---: | :-----: |
{packages}
"""


def parse_package_info(config: pathlib.Path):
    yaml_data = parse_package_config(config)

    name = yaml_data["package"]["name"]
    version = yaml_data["package"]["version"]
    is_library = yaml_data.get("build", {}).get("library", False)

    return name, version, is_library


def get_package_metadata_list(directory: pathlib.Path):
    return directory.glob("**/meta.yaml")


def to_markdown(template: str, packages: Dict[str, Any]):
    packages_table = []
    for name, pkg_info in packages.items():
        version = pkg_info["version"]
        package_info = f"| {name} | {version} |"
        packages_table.append(package_info)

    packages_table = sorted(packages_table, key=lambda name: name.lower())

    return template.format(packages="\n".join(packages_table))


def main():
    packages_root = PACKAGES_DIR
    packages_list = get_package_metadata_list(pathlib.Path(packages_root))

    packages = {}
    for package in packages_list:
        name, version, is_library = parse_package_info(package)

        # skip libraries (e.g. libxml, libyaml, ...)
        if is_library:
            continue

        packages[name] = {
            "name": name,
            "version": version,
        }

    md = to_markdown(TEMPLATE, packages)
    with open(OUTPUT_PATH, "w") as f:
        f.write(md)


if __name__ == "__main__":
    main()
