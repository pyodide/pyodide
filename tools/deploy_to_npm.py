#!/usr/bin/env python3

# Warning: this file needs to work in Python 3.7 since it is used in the deploy
# stage and the docker image cibuilds/github:0.13 is Alpine 3.10 which comes
# with Python 3.7

import subprocess
import sys
from pathlib import Path

from bump_version import python_version_to_js_version

VERSION = python_version_to_js_version(sys.argv[-1])
IS_PRERELEASE = "a" in VERSION
PKG = "pyodide"
PKG = "@hoodmane/hoodmane-test-pyodide"

cwd = Path("./dist")

cmd = ["npm", "publish"]
if IS_PRERELEASE:
    cmd.extend(["--tag", "next"])
result = subprocess.run(cmd, cwd=cwd)
if result.returncode:
    sys.exit(result.returncode)

if not IS_PRERELEASE:
    sys.exit(
        subprocess.run(["npm", "dist-tag", "add", f"{PKG}@{VERSION}", "next"], cwd=cwd)
    )
