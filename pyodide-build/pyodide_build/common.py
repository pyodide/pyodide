import functools
import subprocess
from pathlib import Path
from typing import Iterable, Iterator, Optional

from packaging.tags import Tag, compatible_tags, cpython_tags
from packaging.utils import parse_wheel_filename

PLATFORM = "emscripten_wasm32"


def pyodide_tags() -> Iterator[Tag]:
    """
    Returns the sequence of tag triples for the Pyodide interpreter.

    The sequence is ordered in decreasing specificity.
    """

    yield from cpython_tags(platforms=[PLATFORM])
    yield from compatible_tags(platforms=[PLATFORM])


def find_matching_wheels(wheel_paths: Iterable[Path]) -> Iterator[Path]:
    """
    Returns the sequence wheels whose tags match the Pyodide interpreter.

    Parameters
    ----------
    wheel_paths
        A list of paths to wheels

    Returns
    -------
    The subset of wheel_paths that have tags that match the Pyodide interpreter.
    """
    wheel_paths = list(wheel_paths)
    wheel_tags_list: list[frozenset[Tag]] = []
    for wheel in wheel_paths:
        _, _, _, tags = parse_wheel_filename(wheel.name)
        wheel_tags_list.append(tags)
    for supported_tag in pyodide_tags():
        for wheel_path, wheel_tags in zip(wheel_paths, wheel_tags_list):
            if supported_tag in wheel_tags:
                yield wheel_path


UNVENDORED_STDLIB_MODULES = {"test", "distutils"}

ALWAYS_PACKAGES = {
    "pyparsing",
    "packaging",
    "micropip",
}

CORE_PACKAGES = {
    "micropip",
    "pyparsing",
    "pytz",
    "packaging",
    "Jinja2",
    "regex",
    "fpcast-test",
    "sharedlib-test-py",
    "cpp-exceptions-test",
    "ssl",
}

CORE_SCIPY_PACKAGES = {
    "numpy",
    "scipy",
    "pandas",
    "matplotlib",
    "scikit-learn",
    "joblib",
    "pytest",
}


def _parse_package_subset(query: Optional[str]) -> set[str]:
    """Parse the list of packages specified with PYODIDE_PACKAGES env var.

    Also add the list of mandatory packages: ["pyparsing", "packaging",
    "micropip"]

    Supports following meta-packages,
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

    packages = {el.strip() for el in query.split(",")}
    packages.update(ALWAYS_PACKAGES)
    packages.update(UNVENDORED_STDLIB_MODULES)
    # handle meta-packages
    if "core" in packages:
        packages |= CORE_PACKAGES
        packages.discard("core")
    if "min-scipy-stack" in packages:
        packages |= CORE_PACKAGES | CORE_SCIPY_PACKAGES
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


@functools.cache
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
