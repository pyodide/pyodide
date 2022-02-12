from pathlib import Path
from typing import Optional, Set

import functools
import subprocess

UNVENDORED_STDLIB_MODULES = ["test", "distutils"]


def _parse_package_subset(query: Optional[str]) -> Set[str]:
    """Parse the list of packages specified with PYODIDE_PACKAGES env var.

    Also add the list of mandatory packages: ["pyparsing", "packaging",
    "micropip"]

    Supports folowing meta-packages,
     - 'core': corresponds to packages needed to run the core test suite
       {"micropip", "pyparsing", "pytz", "packaging", "Jinja2", "fpcast-test"}. This is the default option
       if query is None.
     - 'min-scipy-stack': includes the "core" meta-package as well as some of the
       core packages from the scientific python stack and their dependencies:
       {"numpy", "scipy", "pandas", "matplotlib", "scikit-learn", "joblib", "pytest"}.
       This option is non exaustive and is mainly intended to make build faster
       while testing a diverse set of scientific packages.
     - '*': corresponds to all packages (returns None)

    Note: None as input is equivalent to PYODIDE_PACKAGES being unset and leads
    to only the core packages being built.

    Returns:
      a set of package names to build or None (build all packages).
    """
    if query is None:
        query = "core"

    core_packages = {
        "micropip",
        "pyparsing",
        "pytz",
        "packaging",
        "Jinja2",
        "regex",
        "fpcast-test",
        "sharedlib-test-py",
    }
    core_scipy_packages = {
        "numpy",
        "scipy",
        "pandas",
        "matplotlib",
        "scikit-learn",
        "joblib",
        "pytest",
    }
    packages = {el.strip() for el in query.split(",")}
    packages.update(["pyparsing", "packaging", "micropip"])
    packages.update(UNVENDORED_STDLIB_MODULES)
    # handle meta-packages
    if "core" in packages:
        packages |= core_packages
        packages.discard("core")
    if "min-scipy-stack" in packages:
        packages |= core_packages | core_scipy_packages
        packages.discard("min-scipy-stack")

    # Hack to deal with the circular dependence between soupsieve and
    # beautifulsoup4
    if "beautifulsoup4" in packages:
        packages.add("soupsieve")
    packages.discard("")
    return packages


def file_packager_path() -> Path:
    ROOTDIR = Path(__file__).parents[2].resolve()
    return ROOTDIR / "emsdk/emsdk/upstream/emscripten/tools/file_packager"


def invoke_file_packager(
    *,
    name,
    root_dir=".",
    base_dir,
    pyodidedir,
    compress=False,
):
    subprocess.run(
        [
            str(file_packager_path()),
            f"{name}.data",
            f"--js-output={name}.js",
            "--preload",
            f"{base_dir}@{pyodidedir}",
            "--lz4",
            "--export-name=globalThis.__pyodide_module",
            "--exclude",
            "*__pycache__*",
            "--use-preload-plugins",
        ],
        cwd=root_dir,
        check=True,
    )
    if compress:
        subprocess.run(
            [
                "npx",
                "--no-install",
                "terser",
                root_dir / f"{name}.js",
                "-o",
                root_dir / f"{name}.js",
            ],
            check=True,
        )


def get_make_flag(name):
    """Get flags from makefile.envs.

    For building packages we currently use:
        SIDE_MODULE_LDFLAGS
        SIDE_MODULE_CFLAGS
        SIDE_MODULE_CXXFLAGS
        TOOLSDIR
    """
    return get_make_environment_vars()[name]


@functools.lru_cache(maxsize=None)
def get_make_environment_vars():
    """Load environment variables from Makefile.envs

    This allows us to set all build vars in one place"""
    # TODO: make this not rely on paths outside of pyodide-build
    rootdir = Path(__file__).parents[2].resolve()
    environment = {}
    result = subprocess.run(
        ["make", "-f", str(rootdir / "Makefile.envs"), ".output_vars"],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        equalPos = line.find("=")
        if equalPos != -1:
            varname = line[0:equalPos]
            value = line[equalPos + 1 :]
            value = value.strip("'").strip()
            environment[varname] = value
    return environment
