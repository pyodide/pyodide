from pathlib import Path
from typing import Optional, Set
import shutil

ROOTDIR = Path(__file__).parents[1].resolve()
TOOLSDIR = ROOTDIR / "tools"

# Use emcc.py because emcc may be a ccache symlink
_EMCC_PATH = shutil.which("emcc.py")
if _EMCC_PATH is None:
    print("emcc.py not found. Setting file_packager.py path to /dev/null")
    PACKAGERPATH = Path("/dev/null")
else:
    PACKAGERPATH = Path(_EMCC_PATH).parent / "tools" / "file_packager.py"

TARGETPYTHON = ROOTDIR / "cpython" / "installs" / "python-3.8.2"
# Leading space so that argparse doesn't think this is a flag
DEFAULTCFLAGS = " -fPIC"
DEFAULTCXXFLAGS = ""
# fmt: off
DEFAULTLDFLAGS = " ".join(
    [
        "-O2",
        "-Werror",
        "-s", "EMULATE_FUNCTION_POINTER_CASTS=1",
        "-s", "SIDE_MODULE=1",
        "-s", "WASM=1",
        "-s", "BINARYEN_TRAP_MODE='clamp'",
        "--memory-init-file", "0",
        "-s", "LINKABLE=1",
        "-s", "EXPORT_ALL=1",
    ]
)
# fmt: on


def parse_package(package):
    # Import yaml here because pywasmcross needs to run in the built native
    # Python, which won't have PyYAML
    import yaml

    # TODO: Validate against a schema
    with open(package) as fd:
        return yaml.safe_load(fd)


def _parse_package_subset(query: Optional[str]) -> Optional[Set[str]]:
    """Parse the list of packages specified with PYODIDE_PACKAGES env var.

    Also add the list of mandatory packages: ['micropip', 'distlib']

    Returns:
      a set of package names to build or None.
    """
    if query is None:
        return None
    packages = query.split(",")
    packages = [el.strip() for el in packages]
    packages = ["micropip", "distlib"] + packages
    return set(packages)
