#!/usr/bin/env python3
import sys
from pathlib import Path


def main():
    try:
        import pyodide_build
    except ImportError:
        sys.exit(1)

    install_path = Path(pyodide_build.__path__[0])
    editable_install_path = Path(__file__).parents[1] / "pyodide-build/pyodide_build"

    sys.exit(install_path != editable_install_path)


if __name__ == "__main__":
    main()
