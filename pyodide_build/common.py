from pathlib import Path
from typing import Optional, Set
import shutil

ROOTDIR = Path(__file__).parents[1].resolve()
TOOLSDIR = ROOTDIR / "tools"
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
        "-s",'BINARYEN_EXTRA_PASSES="--pass-arg=max-func-params@61"',
        "-s", "SIDE_MODULE=1",
        "-s", "WASM=1",
        "--memory-init-file", "0",
        "-s", "LINKABLE=1",
        "-s", "EXPORT_ALL=1",
    ]
)
# fmt: on


def _parse_package_subset(query: Optional[str]) -> Optional[Set[str]]:
    """Parse the list of packages specified with PYODIDE_PACKAGES env var.

    Also add the list of mandatory packages: ['micropip', 'distlib']

    Returns:
      a set of package names to build or None.
    """
    if query is None:
        return None
    packages = {el.strip() for el in query.split(",")}
    packages.update(["micropip", "distlib"])
    packages.discard("")
    return set(packages)


def file_packager_path() -> Path:
    # Use emcc.py because emcc may be a ccache symlink
    emcc_path = shutil.which("emcc.py")
    if emcc_path is None:
        raise RuntimeError(
            "emcc.py not found. Setting file_packager.py path to /dev/null"
        )

    return Path(emcc_path).parent / "tools" / "file_packager.py"
