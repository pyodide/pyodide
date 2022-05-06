"""
Check whether a given CI job needs to be run in PRs given
the changed files with respect to upstream/main
"""
import argparse
import fnmatch
import os
from subprocess import check_call, check_output

# When one of the following paths match in the git diff,
# their corresponding CI step will run
CI_DEPENDENCIES = {
    "build_packages": [
        "packages/*",
        "cpython/*",
        "emsdk/*",
        "Makefile*",
        ".circleci/*",
        "conftest.py",
        "src/core/*",
        "src/*.js",
        "benchmark/*",
        "pyodide_build/*",
        "tools/*",
    ],
    # + all build_packages patterns, see below
    # since core is a dependency of build packages. The above
    # file patterns do not need to be repeated.
    "build_core": ["src/tests/*", "src/pyodide-py/*"],
}


def git_get_files_changed(head="HEAD", origin: str | None = None) -> list[str]:
    """Get list of files changed in the current git branch

    As compared to latest common commit between the `head` branch
    and the `origin` branch.
    """
    if origin is None:
        if "CI" in os.environ:
            origin = "origin/main"
        else:
            origin = "upstream/main"

    base_commit = check_output(
        ["git", "merge-base", origin, head], encoding="utf-8"
    ).strip()
    file_names = check_output(
        ["git", "diff", "--name-only", base_commit], encoding="utf-8"
    ).strip()
    return file_names.split("\n")


def check_ci_job_required(step: str, files_changed: list[str]) -> bool:
    """Check if a given CI job needs to run given modified files"""
    if step not in CI_DEPENDENCIES:
        raise ValueError

    if step == "build_core":
        if check_ci_job_required("build_packages", files_changed):
            print(f"CI job={step} is required by the build_packages job")
            return True

    pattern_matched = []
    for pattern in CI_DEPENDENCIES[step]:
        if fnmatch.filter(files_changed, pattern):
            pattern_matched.append(pattern)

    if pattern_matched:
        print(
            f"CI job={step} is required due to " f"following file patterns matching:",
            end="",
        )
        prefix = "\n    - "
        print(prefix + prefix.join(pattern_matched))
        return True
    return False


def make_parser(parser):
    parser.description = (
        "Determine if a CI job needs to run.\n\n"
        "If not will be cancelled in CircleCI."
    )
    parser.add_argument("job_name", type=str, help="Name of the CI job")
    return parser


def main(args):
    files_changed = git_get_files_changed()
    if files_changed:
        prefix = "\n    - "
        print("Detected following changed files:", end="")
        print(prefix + prefix.join(files_changed))
    run_job = check_ci_job_required(args.job_name, files_changed)
    if not run_job:
        print("Skipping CI job as none of the required files patterns matched.")
        if "CIRCLECI" in os.environ:
            check_call(["circleci", "step", "halt"])


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
