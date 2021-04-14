from pathlib import Path
from typing import Optional, Set
import shutil
import subprocess
import functools


def _parse_package_subset(query: Optional[str]) -> Optional[Set[str]]:
    """Parse the list of packages specified with PYODIDE_PACKAGES env var.

    Also add the list of mandatory packages: ["pyparsing", "packaging", "micropip"]

    Returns:
      a set of package names to build or None.
    """
    if query is None:
        return None
    packages = {el.strip() for el in query.split(",")}
    packages.update(["pyparsing", "packaging", "micropip"])
    packages.discard("")
    return packages


def file_packager_path() -> Path:
    # Use emcc.py because emcc may be a ccache symlink
    emcc_path = shutil.which("emcc.py")
    if emcc_path is None:
        raise RuntimeError(
            "emcc.py not found. Setting file_packager.py path to /dev/null"
        )

    return Path(emcc_path).parent / "tools" / "file_packager.py"


def get_make_flag(name):
    """Get flags from makefile.envs,
        e.g. For building packages we currently use:
    SIDE_MODULE_LDFLAGS
    SIDE_MODULE_CFLAGS
    SIDE_MODULE_CXXFLAGS
    TOOLSDIR
    """
    return get_make_environment_vars()[name]


@functools.lru_cache(maxsize=None)
def get_make_environment_vars():
    """Load environment variables from Makefile.envs, this allows us to set all build vars in one place"""
    __ROOTDIR = Path(__file__).parents[1].resolve()
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
