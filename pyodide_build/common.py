from pathlib import Path
from typing import Optional, Set

ROOTDIR = Path(__file__).parents[1].resolve() / "tools"
TARGETPYTHON = ROOTDIR / ".." / "cpython" / "installs" / "python-3.8.2"
DEFAULTCFLAGS = ""
# fmt: off
DEFAULTLDFLAGS = " ".join(
    [
        "-O2",
        "-s", "BINARYEN_METHOD='native-wasm'",
        "-Werror",
        "-s", "EMULATED_FUNCTION_POINTERS=1",
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
