from pathlib import Path
from typing import Optional, Set
import subprocess
import functools

UNVENDORED_STDLIB_MODULES = ["test", "distutils"]


def _parse_package_subset(query: Optional[str]) -> Optional[Set[str]]:
    """Parse the list of packages specified with PYODIDE_PACKAGES env var.

    Also add the list of mandatory packages: ["pyparsing", "packaging",
    "micropip"]

    Returns:
      a set of package names to build or None.
    """
    if query is None:
        return None
    packages = {el.strip() for el in query.split(",")}
    packages.update(["pyparsing", "packaging", "micropip"])
    # Hack to deal with the circular dependence between soupsieve and
    # beautifulsoup4
    if "beautifulsoup4" in packages:
        packages.add("soupsieve")
    packages.discard("")
    return packages


def file_packager_path() -> Path:
    ROOTDIR = Path(__file__).parents[2].resolve()
    return ROOTDIR / "tools" / "file_packager.sh"


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
    __ROOTDIR = Path(__file__).parents[2].resolve()
    environment = {}
    result = subprocess.run(
        ["make", "-f", str(__ROOTDIR / "Makefile.envs"), ".output_vars"],
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
