import argparse
import sys
from pathlib import Path

from virtualenv import session_via_cli

parser = argparse.ArgumentParser("create_pyodide_venv")
parser.add_argument("dest", help="directory to create virtualenv at", type=str)
args = parser.parse_args()
dest = Path(args.dest)

if dest.exists():
    print(f"dest directory '{dest}' already exists")
    sys.exit(1)


version_major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
session = session_via_cli(["--no-wheel", "-p", "tools/python.js", str(dest)])
pyodide_version = session.interpreter.version.partition(" ")[0].split(".")
if sys.version_info.major != int(pyodide_version[0]) or sys.version_info.minor != int(
    pyodide_version[1]
):
    expected_version = ".".join(pyodide_version[:2])
    print(
        f"Expected host Python version to be {expected_version} but got version {version_major_minor}"
    )
    sys.exit(1)

session.run()

dest = Path(session.creator.dest).absolute()
(dest / "pip.conf").write_text(
    """\
[install]
only-binary=:all:
find-links=/home/hood/Documents/programming/pyodide/dist/
"""
)

host_python_path = dest / "bin/python3.10-host"
host_python_path.symlink_to(sys.executable)
pip_path = dest / "bin" / "pip"
pip_path.write_text(
    f"""\
#!{host_python_path}
# -*- coding: utf-8 -*-
import os
os.environ["_PYTHON_HOST_PLATFORM"] = "emscripten_3_1_14_wasm32"

import re
import sys
from pip._internal.cli.main import main
if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])
    sys.exit(main())
"""
)
pip_path.chmod(0o777)

other_pips = [
    dest / "bin" / "pip3",
    dest / "bin" / f"pip{version_major_minor}",
    dest / "bin" / f"pip-{version_major_minor}",
]

for pip in other_pips:
    pip.unlink()
    pip.symlink_to(pip_path)
