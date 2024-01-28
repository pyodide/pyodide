#!/usr/bin/env python3

import shutil
import subprocess
import warnings
from pathlib import Path

from ruamel.yaml import YAML

from .common import _get_sha256_checksum
from .logger import logger
from .mkpkg import run_prettier


def update_package_sage(
    root: Path,
    package: str,
    sage_root: Path,
) -> None:
    sage_version = (sage_root / "src" / "VERSION.txt").read_text().strip()
    sage_version = sage_version.replace('.beta', 'b').replace('.rc', 'rc')
    sage_upstream = sage_root / "upstream"

    yaml = YAML()
    meta_path = root / package / "meta.yaml"
    yaml_content = yaml.load(meta_path.read_bytes())

    sdist_name = f"{package}-{sage_version}.tar.gz"
    sdist_path = sage_root / "upstream" / sdist_name
    yaml_content["source"]["url"] = f"file://{sdist_path}"
    yaml_content["source"].pop("md5", None)
    yaml_content["source"]["sha256"] = _get_sha256_checksum(sdist_path)
    yaml_content["package"]["version"] = sage_version

    yaml.representer.ignore_aliases = lambda *_: True
    yaml.dump(yaml_content, meta_path)
    try:
        run_prettier(meta_path)
    except FileNotFoundError:
        warnings.warn("'npx' executable missing, output has not been prettified.")

    logger.success(f"Updated {package}.")
