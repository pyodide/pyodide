from pathlib import Path
from typing import Optional, Set
import shutil
import subprocess


ROOTDIR = Path(__file__).parents[1].resolve()
TOOLSDIR = ROOTDIR / "tools"
TARGETPYTHON = ROOTDIR / "cpython" / "installs" / "python-3.8.2"

# Leading space so that argparse doesn't think this is a flag
# default flags are all loaded from Makefile.envs (see loadMakefileEnvs() below)
DEFAULTCFLAGS = " "
DEFAULTCXXFLAGS = " "
DEFAULTLDFLAGS = " "


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
    return packages


def file_packager_path() -> Path:
    # Use emcc.py because emcc may be a ccache symlink
    emcc_path = shutil.which("emcc.py")
    if emcc_path is None:
        raise RuntimeError(
            "emcc.py not found. Setting file_packager.py path to /dev/null"
        )

    return Path(emcc_path).parent / "tools" / "file_packager.py"


def loadMakefileEnvs():
    """ Load environment variables from Makefile.envs, this allows us to set all build vars in one place
    """
    global DEFAULTLDFLAGS,DEFAULTCFLAGS,DEFAULTCXXFLAGS
    result=subprocess.run(["make","-f",str(ROOTDIR/"Makefile.envs"),".output_vars"],capture_output=True,text=True)
    for line in result.stdout.splitlines():
        equalPos=line.find("=")
        if equalPos!=-1:
            varname=line[0:equalPos]
            value=line[equalPos+1:]
            value=value.strip("'").strip()
            if varname=="SIDE_MODULE_LDFLAGS":
                DEFAULTLDFLAGS=value
            if varname=="SIDE_MODULE_CFLAGS":
                DEFAULTCFLAGS=value
            if varname=="SIDE_MODULE_CXXFLAGS":
                DEFAULTCXXFLAGS=value

# load the environment variables from Makefile.envs so that they are all in the same place
loadMakefileEnvs()
