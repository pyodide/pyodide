#!/usr/bin/env python3
"""
Create a GitHub release for a Pyodide tag with the ghr tool.

For stable releases, the release body links to the section of the changelog for
the released version. For alpha releases, we link to the changelog in the
repository at the tag.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

CHANGELOG_PATH = Path(__file__).parents[1] / "docs/project/changelog.md"
CHANGELOG_URL = "https://pyodide.org/en/stable/project/changelog.html"
CHANGELOG_TOP_ANCHOR = "change-log"
CHANGELOG_PRERELEASE_URL = (
    "https://github.com/pyodide/pyodide/blob/{tag}/docs/project/changelog.md#unreleased"
)


def changelog_anchor(tag: str, changelog_path: Path = CHANGELOG_PATH) -> str:
    """The anchor of the changelog section for ``tag``.

    Sphinx generates section ids by lowercasing the title and replacing each
    run of non-alphanumeric characters with a dash.

    >>> changelog_anchor("314.0.3")
    'version-314-0-3'
    >>> changelog_anchor("0.29.4")
    'version-0-29-4'

    If there is no section for the tag, link to the top of the page:

    >>> changelog_anchor("999.0.0")
    'change-log'
    """
    title = f"Version {tag}"
    if not has_changelog_section(title, changelog_path):
        return CHANGELOG_TOP_ANCHOR
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def has_changelog_section(title: str, changelog_path: Path = CHANGELOG_PATH) -> bool:
    if not changelog_path.exists():
        return False
    pattern = re.compile(rf"^##\s+{re.escape(title)}\s*$", re.MULTILINE)
    return pattern.search(changelog_path.read_text()) is not None


def release_body(tag: str, changelog_path: Path = CHANGELOG_PATH) -> str:
    """The body of the GitHub release.

    >>> release_body("314.0.3")
    'See changes at https://pyodide.org/en/stable/project/changelog.html#version-314-0-3'
    >>> release_body("314.0.0a1")
    'See changes at https://github.com/pyodide/pyodide/blob/314.0.0a1/docs/project/changelog.md#unreleased'
    """
    if is_prerelease(tag):
        return f"See changes at {CHANGELOG_PRERELEASE_URL.format(tag=tag)}"
    anchor = changelog_anchor(tag, changelog_path)
    return f"See changes at {CHANGELOG_URL}#{anchor}"


def is_prerelease(tag: str) -> bool:
    return "a" in tag


def ghr_args(
    tag: str,
    dist_dir: Path,
    token: str,
    owner: str,
    repo: str,
    commit: str,
    ghr_bin: str,
    changelog_path: Path = CHANGELOG_PATH,
) -> list[str]:
    """Build the ghr command line.

    Options have to come first, the last two arguments have to be the tag and
    the directory with the release assets.
    """
    args = [
        ghr_bin,
        "-t",
        token,
        "-u",
        owner,
        "-r",
        repo,
        "-c",
        commit,
        "-b",
        release_body(tag, changelog_path),
        # TODO: Should we get rid of -delete?
        "-delete",
    ]
    if is_prerelease(tag):
        args.append("-prerelease")
    args += [tag, str(dist_dir)]
    return args


def redact(args: list[str], token: str) -> str:
    return " ".join("$GITHUB_TOKEN" if arg == token else arg for arg in args)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dist_dir", type=Path, help="Directory with the release assets to upload"
    )
    parser.add_argument("--tag", required=True, help="Tag to release")
    parser.add_argument("--commit", required=True, help="Commit to release")
    parser.add_argument("--owner", required=True, help="GitHub owner of the repository")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--ghr-bin", default="ghr", help="Path to the ghr binary")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the ghr command instead of running it",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token and not args.dry_run:
        sys.exit("GITHUB_TOKEN is not set")

    cmd = ghr_args(
        tag=args.tag,
        dist_dir=args.dist_dir,
        token=token,
        owner=args.owner,
        repo=args.repo,
        commit=args.commit,
        ghr_bin=args.ghr_bin,
    )
    print(redact(cmd, token))
    if args.dry_run:
        return
    sys.exit(subprocess.run(cmd, check=False).returncode)


if __name__ == "__main__":
    main()
