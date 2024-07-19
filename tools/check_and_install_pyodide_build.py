#!/usr/bin/env python3
import sys
import subprocess as sp

PYODIDE_BUILD_REPO: str = "https://github.com/pyodide/pyodide-build"
PYODIDE_BUILD_COMMIT: str = "fac0109aa2acf14469320b049d710dd42639bf94"  # v0.27.3

def get_pyodide_build_install_url() -> str | None:
    """
    Return the version of the pyodide-build package or the URL to the repository.
    """
    freeze_result = sp.check_output([
        sys.executable, "-m", "pip", "freeze",
    ])

    for line in freeze_result.decode().split("\n"):
        if line.startswith("pyodide-build"):
            try:
                return line.split(" @ ")[1]
            except IndexError:
                raise ValueError("pyodide-build is not installed from a VCS")

    return None


def main():
    install_url = f"git+{PYODIDE_BUILD_REPO}@{PYODIDE_BUILD_COMMIT}"
    installed_url = get_pyodide_build_install_url()

    if not installed_url or installed_url != install_url:
        sp.check_call([
            sys.executable, "-m", "pip", "install", install_url,
        ])


if __name__ == "__main__":
    main()
