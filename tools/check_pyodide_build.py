#!/usr/bin/env python3
import sys


def main():
    try:
        import pyodide_build

        version = pyodide_build.__version__
        required_version = sys.argv[1]
    except Exception:
        sys.exit(1)

    sys.exit(version != required_version)


if __name__ == "__main__":
    main()
