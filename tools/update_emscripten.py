#!/usr/bin/env python3

import argparse
import subprocess
import sys
from pathlib import Path

from common import PYODIDE_ROOT, get_makefile_envs

EMSDK = PYODIDE_ROOT / "emsdk"
EMSCRIPTEN = EMSDK / "emscripten"
PATCHES = EMSDK / "patches"


def run(args: list[str | Path], check=True, **kwargs):
    print(" ".join(str(x) for x in args))
    result = subprocess.run(args, check=False, text=True, **kwargs)
    if check and result.returncode:
        sys.exit(result.returncode)
    return result


def setup_emscripten(oldtag: str):
    if not EMSCRIPTEN.exists():
        run(
            ["git", "clone", "git@github.com:emscripten-core/emscripten.git"],
            cwd=EMSCRIPTEN.parent,
        )
    run(["git", "fetch", "origin", "--tags", "--force"], cwd=EMSCRIPTEN)
    run(["git", "config", "rerere.enabled", "true"], cwd=EMSCRIPTEN)
    run(["git", "config", "rerere.autoupdate", "true"], cwd=EMSCRIPTEN)


def rebase(oldtag: str, newtag: str):
    run(["git", "checkout", oldtag, "--quiet"], cwd=EMSCRIPTEN)
    run(["git", "switch", "-C", f"pyodide-{newtag}"], cwd=EMSCRIPTEN)
    patches = sorted(PATCHES.glob("*"))
    run(["git", "am", *patches], cwd=EMSCRIPTEN)
    result = run(
        ["git", "rebase", oldtag, "--onto", newtag], cwd=EMSCRIPTEN, check=False
    )
    while True:
        if result.returncode == 0:
            return
        result = run(
            ["git", "diff", "--quiet"],
            check=False,
            cwd=EMSCRIPTEN,
        )
        if result.returncode != 0:
            print(
                "There were rebase conflicts. Resolve the conflicts and then run again."
            )
            sys.exit(1)
        result = run(["git", "rebase", "--continue"], check=False, cwd=EMSCRIPTEN)


def update_patches(newtag: str):
    # First delete existing patches
    for file in PATCHES.glob("*"):
        file.unlink()
    # Then git format-patch
    run(["git", "format-patch", newtag, "-o", PATCHES], cwd=EMSCRIPTEN)


def update_makefile_envs(newtag):
    # TODO: Implement me!
    pass


def parse_args():
    parser = argparse.ArgumentParser("Update the Emscripten version")
    parser.add_argument("newtag")
    return parser.parse_args()


def main():
    args = parse_args()
    newtag = args.newtag
    oldtag = get_makefile_envs()["PYODIDE_EMSCRIPTEN_VERSION"]
    setup_emscripten(oldtag)
    rebase(oldtag, newtag)
    update_patches(newtag)
    update_makefile_envs(newtag)


if __name__ == "__main__":
    main()
