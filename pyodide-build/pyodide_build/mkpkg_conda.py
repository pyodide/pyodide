#!/usr/bin/env python3

import shutil
import subprocess
import warnings
from pathlib import Path

from ruamel.yaml import YAML

from .logger import logger
from .mkpkg import run_prettier

_conda_to_pyodide = {
    "gmp": "libgmp",
    "mpfr": "libmpfr",
    "mpfi": "libmpfi",
    "mpc": "libmpc",
    "libflint": "flint",
}


def conda_requirement_to_pyodide(requirement: str):
    conda_package = requirement.split(maxsplit=1)[0]  # drop version specifiers
    return _conda_to_pyodide.get(conda_package, conda_package)


def make_package_conda(
    packages_dir: Path,
    package: str,
    version: str | None = None,
) -> None:
    """
    Creates a template for a pyodide meta.yaml from a conda-forge meta.yaml
    """
    logger.info(f"Creating meta.yaml package for {package}")

    yaml = YAML()

    package_dir = packages_dir / package
    package_dir.mkdir(parents=True, exist_ok=True)

    feedstock_dir = package_dir / "feedstock"
    if feedstock_dir.exists():
        logger.info(f"Using existing {feedstock_dir}")
    else:
        feedstock_url = f"https://github.com/conda-forge/{package}-feedstock"
        subprocess.run(
            ["git", "clone", "--depth", "1", feedstock_url, str(feedstock_dir)]
        )

    from conda_build.metadata import MetaData

    conda_metadata = MetaData(feedstock_dir)
    # print(conda_metadata)

    patches = conda_metadata.get_value("source/0/patches")
    for patch in patches:
        (package_dir / patch).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(conda_metadata.path) / patch, package_dir / patch)

    yaml_content = {
        "package": {
            "name": package,
            "version": conda_metadata.version(),
        },
        "source": {
            "url": conda_metadata.get_value("source/0/url")[0],
            "sha256": conda_metadata.get_value("source/0/sha256"),
            "patches": patches,
        },
        "requirements": {
            "host": [
                conda_requirement_to_pyodide(req)
                for req in conda_metadata.get_value("requirements/host")
            ],
            "run": [
                conda_requirement_to_pyodide(req)
                for req in conda_metadata.get_value("requirements/run")
            ],
        },
        "about": {
            "home": conda_metadata.get_value("about/home"),
            "summary": conda_metadata.get_value("about/summary"),
            "license": conda_metadata.get_value("about/license"),
        },
    }

    meta_path = package_dir / "meta.yaml"
    ## if meta_path.exists():
    ##     raise MkpkgFailedException(f"The package {package} already exists")

    yaml.representer.ignore_aliases = lambda *_: True
    yaml.dump(yaml_content, meta_path)
    try:
        run_prettier(meta_path)
    except FileNotFoundError:
        warnings.warn("'npx' executable missing, output has not been prettified.")

    logger.success(f"Output written to {meta_path}")
