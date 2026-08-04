#!/usr/bin/env python3
"""
Trigger a run of the "Release Cross-build environment" GitHub Actions workflow
in the pyodide-build-environment-nightly repo, building the cross-build
environment for the current Pyodide branch.

Before triggering the workflow, check that:
  - the working tree is clean
  - the current branch is up to date with its upstream
"""

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from common import PYODIDE_ROOT, get_makefile_envs

XBUILDENV_REPO_SLUG = "pyodide/pyodide-build-environment-nightly"
WORKFLOW = "publish.yml"


def run(
    args: list[str | Path], check: bool = True, **kwargs: Any
) -> subprocess.CompletedProcess[Any]:
    print(" ".join(str(x) for x in args))
    result = subprocess.run(args, check=False, text=True, **kwargs)
    if check and result.returncode:
        sys.exit(result.returncode)
    return result


def check_working_tree_clean() -> None:
    result = run(
        ["git", "status", "--porcelain"],
        cwd=PYODIDE_ROOT,
        capture_output=True,
    )
    if result.stdout.strip():
        print("Working tree is not clean. Commit or stash your changes first:")
        print(result.stdout)
        sys.exit(1)


def get_current_branch() -> str:
    result = run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=PYODIDE_ROOT,
        capture_output=True,
    )
    branch = result.stdout.strip()
    if branch == "HEAD":
        print("Currently in a detached HEAD state. Check out a branch first.")
        sys.exit(1)
    return branch


def check_branch_pushed(branch: str) -> None:
    upstream = run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        cwd=PYODIDE_ROOT,
        capture_output=True,
        check=False,
    )
    if upstream.returncode:
        print(
            f"Branch '{branch}' has no upstream tracking branch. "
            f"Push it first, e.g.:\n  git push -u origin {branch}"
        )
        sys.exit(1)

    upstream_ref = upstream.stdout.strip()
    remote = upstream_ref.split("/", 1)[0]
    run(["git", "fetch", remote, branch], cwd=PYODIDE_ROOT)

    local_head = run(
        ["git", "rev-parse", "HEAD"], cwd=PYODIDE_ROOT, capture_output=True
    ).stdout.strip()
    remote_head = run(
        ["git", "rev-parse", upstream_ref], cwd=PYODIDE_ROOT, capture_output=True
    ).stdout.strip()

    if local_head != remote_head:
        print(
            f"Local branch '{branch}' is not in sync with '{upstream_ref}'. "
            "Push your changes first."
        )
        sys.exit(1)


def get_python_version() -> str:
    env = get_makefile_envs()
    return f"{env['PYMAJOR']}.{env['PYMINOR']}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--name",
        help=(
            "Name/tag for the release (default: YYYYMMDD-<current branch>, "
            "with '/' replaced by '-')"
        ),
    )
    parser.add_argument(
        "--python-version",
        help="Python version to build with (default: read from Makefile.envs)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the command that would be run, without triggering the workflow",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    check_working_tree_clean()
    branch = get_current_branch()
    check_branch_pushed(branch)

    name = args.name or f"{datetime.now(UTC):%Y%m%d}-{branch.replace('/', '-')}"
    python_version = args.python_version or get_python_version()

    command = [
        "gh",
        "workflow",
        "run",
        WORKFLOW,
        "--repo",
        XBUILDENV_REPO_SLUG,
        "--ref",
        "main",
        "-f",
        f"branch={branch}",
        "-f",
        f"release_version={name}",
        "-f",
        f"python_version={python_version}",
    ]

    if args.dry_run:
        print("Dry run, would execute:")
        print(" ".join(command))
        return

    run(command)


if __name__ == "__main__":
    main()
