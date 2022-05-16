import argparse
import os
from pathlib import Path

from doit.reporter import ZeroReporter

import pyodide_build.buildpkg

DOIT_CONFIG = {
    "verbosity": 2,
    "minversion": "0.36.0",
    "reporter": ZeroReporter,
}


def task_build_package():
    def build_package(name):
        parser = pyodide_build.buildpkg.make_parser(argparse.ArgumentParser())
        args = parser.parse_args([name])
        pyodide_build.buildpkg.main(args)

    return {
        "actions": [(build_package,)],
        "params": [
            {
                "name": "name",
                "long": "name",
                "type": str,
                "default": "",
            }
        ],
    }


def task_build_cpython():
    pyodide_root = Path(os.environ["PYODIDE_ROOT"])
    cpythonlib = os.environ["CPYTHONLIB"]
    return {
        "file_dep": [pyodide_root / "cpython/Makefile"],
        # "actions": ["make -C cpython", f"pip install tzdata --target={cpythonlib}"],
        "actions": ["make -C cpython"],
        "targets": [
            pyodide_root / cpythonlib / "libpython3.10.a",
            pyodide_root / cpythonlib / "tzdata",
        ],
        "task_dep": ["build_emsdk"],
    }


def task_build_emsdk():
    pyodide_root = Path(os.environ["PYODIDE_ROOT"])
    return {
        "file_dep": [pyodide_root / "emsdk/Makefile"],
        "actions": ["make -C emsdk"],
        "targets": [pyodide_root / "emsdk/emsdk/.complete"],
    }
