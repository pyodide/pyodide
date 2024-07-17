#!/usr/bin/env python3
import os
import sys


def main():
    if os.environ.get("SKIP_PYODIDE_BUILD_CHECK"):
        sys.exit(0)

    try:
        import pyodide_build

        version = pyodide_build.__version__
        required_version = sys.argv[1]
    except Exception:
        sys.exit(1)

    sys.exit(version != required_version)


if __name__ == "__main__":
    main()
