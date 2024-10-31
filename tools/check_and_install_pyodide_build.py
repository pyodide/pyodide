#!/usr/bin/env python3
import argparse
import subprocess as sp
import sys


def get_pyodide_build_install_url() -> str | None:
    """
    Return the version of the pyodide-build package or the URL to the repository.
    """
    freeze_result = sp.check_output(
        [
            sys.executable,
            "-m",
            "pip",
            "freeze",
        ]
    )

    for line in freeze_result.decode().split("\n"):
        if line.startswith("pyodide-build"):
            try:
                return line.split(" @ ")[1]
            except IndexError:
                print("pyodide-build is not installed from a VCS: ", line)
                return None

    return None


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("commit", type=str)
    parser.add_argument(
        "--repo", type=str, default="https://github.com/pyodide/pyodide-build"
    )

    return parser.parse_args()


def main():
    args = parse_args()
    install_url = f"git+{args.repo}@{args.commit}"
    installed_url = get_pyodide_build_install_url()

    if not installed_url or installed_url != install_url:
        sp.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                install_url,
            ]
        )


if __name__ == "__main__":
    main()
