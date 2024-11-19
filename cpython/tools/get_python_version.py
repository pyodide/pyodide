# https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#python-requires

import sys
import tomllib

if __name__ == "__main__":
    with open("../pyproject.toml", "rb") as in_file:
        requires_python = (
            tomllib.load(in_file).get("project", {}).get("requires-python")
        )
    assert requires_python, "requires-python not found in ../pyproject.toml"
    sys.stdout.write(f"{requires_python}\n")
