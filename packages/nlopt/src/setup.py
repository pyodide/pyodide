#!/usr/bin/env python
import os
import re
from pathlib import Path
from subprocess import check_call
from setuptools import setup, Extension
from setuptools.command.build_py import build_py
from numpy import get_include


def create_init_py_file():
    with open("CMakeLists.txt") as f:
        content = f.read()
        version = []
        for s in ("MAJOR", "MINOR", "BUGFIX"):
            m = re.search(f"NLOPT_{s}_VERSION *['\"](.+)['\"]", content)
            version.append(m.group(1))
        version = ".".join(version)

    pkg_folder = Path("nlopt")
    pkg_folder.mkdir(exist_ok=True)
    with (pkg_folder / "__init__.py").open("w") as f:
        f.write(
            f"""
from .nlopt import *

__version__ = '{version}'
    """.strip()
            + "\n"
        )

    return version


version = create_init_py_file()


setup(
    name="nlopt",
    version=version,
    packages=["nlopt"],
    install_requires=["numpy >=1.14"],
    zip_safe=False,
    # package_data = {
    #     'nlopt': ['nlopt/_nlopt.so']
    # },
    include_package_data = True, 
)
