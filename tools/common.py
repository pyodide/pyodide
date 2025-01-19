import subprocess
import sys
from pathlib import Path

PYODIDE_ROOT = Path(__file__).parents[1]


def get_makefile_envs():
    result = subprocess.run(
        ["make", "-f", str(PYODIDE_ROOT / "Makefile.envs"), ".output_vars"],
        capture_output=True,
        text=True,
        env={"PYODIDE_ROOT": str(PYODIDE_ROOT)},
        check=False,
    )

    if result.returncode != 0:
        print("ERROR: Failed to load environment variables from Makefile.envs")
        sys.exit(1)

    environment = {}
    for line in result.stdout.splitlines():
        equalPos = line.find("=")
        if equalPos != -1:
            varname = line[0:equalPos]

            value = line[equalPos + 1 :]
            value = value.strip("'").strip()
            environment[varname] = value

    return environment
