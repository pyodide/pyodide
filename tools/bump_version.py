#!/usr/bin/env python3

import argparse
import difflib
import functools
import itertools
import pathlib
import re
from ast import Constant
from collections import namedtuple
from collections.abc import Callable

CORE_VERSION_REGEX = r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"

PYTHON_VERSION_REGEX = CORE_VERSION_REGEX + (
    r"((?P<pre>a|b|rc)(?P<preversion>\d+))?" r"(\.(?P<dev>dev)(?P<devversion>\d+))?"
)

JS_VERSION_REGEX = CORE_VERSION_REGEX + (
    r"(\-(?P<pre>alpha|beta|rc)\.(?P<preversion>\d+))?"
    r"(\-(?P<dev>dev)\.(?P<devversion>\d+))?"
)


def build_version_pattern(pattern):
    return re.compile(
        pattern.format(
            python_version=f"(?P<version>{PYTHON_VERSION_REGEX})",
            js_version=f"(?P<version>{JS_VERSION_REGEX})",
        )
    )


ROOT = pathlib.Path(__file__).resolve().parent.parent
Target = namedtuple("target", ("file", "pattern", "prerelease"))
PYTHON_TARGETS = [
    Target(
        file=ROOT / "Makefile.envs",
        pattern=build_version_pattern(r"PYODIDE_VERSION \?= {python_version}"),
        prerelease=True,
    ),
    Target(
        file=ROOT / "src/py/pyodide/__init__.py",
        pattern=build_version_pattern('__version__ = "{python_version}"'),
        prerelease=True,
    ),
    Target(
        file=ROOT / "src/py/pyproject.toml",
        pattern=build_version_pattern('version = "{python_version}"'),
        prerelease=True,
    ),
    Target(
        ROOT / "docs/project/about.md",
        build_version_pattern(r"version\s*=\s*{{{python_version}}}"),
        prerelease=False,
    ),
    Target(
        ROOT / "src/js/version.ts",
        build_version_pattern('version: string = "{python_version}"'),
        prerelease=True,
    ),
    Target(
        ROOT / "src/core/pre.js",
        build_version_pattern('API.version = "{python_version}"'),
        prerelease=True,
    ),
]

JS_TARGETS = [
    Target(
        ROOT / "src/js/package.json",
        build_version_pattern(r'"pyodide",\s*"version": "{js_version}"'),
        prerelease=True,
    ),
    Target(
        ROOT / "src/js/package-lock.json",
        build_version_pattern(r'"pyodide",\s*"version": "{js_version}"'),
        prerelease=True,
    ),
]


@functools.lru_cache
def python_version_to_js_version(version: str) -> Constant:
    """
    Convert Python version name to JS version name
    These two are different in prerelease or dev versions.
    e.g. 1.2.3a0 <==> 1.2.3-alpha.0
         4.5.6.dev2 <==> 4.5.6-dev.2
    """
    match = re.match(PYTHON_VERSION_REGEX, version)
    matches = match.groupdict()

    prerelease = matches["pre"] is not None
    devrelease = matches["dev"] is not None

    if prerelease and devrelease:
        raise ValueError("Cannot have both prerelease and devrelease")
    elif prerelease:
        matches["pre"] = matches["pre"].replace("a", "alpha").replace("b", "beta")
        return "{major}.{minor}.{patch}-{pre}.{preversion}".format(**matches)
    elif devrelease:
        return "{major}.{minor}.{patch}-{dev}.{devversion}".format(**matches)
    else:
        return "{major}.{minor}.{patch}".format(**matches)


@functools.lru_cache
def is_core_version(version: str) -> bool:
    match = re.fullmatch(CORE_VERSION_REGEX, version)
    if match is None:
        return False

    return True


def parse_current_version(target: Target) -> str:
    """Parse current version"""
    content = target.file.read_text()
    match = target.pattern.search(content)

    if match is None:
        raise ValueError(f"Unable to detect version string: {target.file}")

    return match.groupdict()["version"]


def generate_updated_content(
    target: Target, current_version: str, new_version: str
) -> Callable:
    file = target.file
    pattern = target.pattern
    content = file.read_text()

    if current_version == new_version:
        return None

    # Some files only required to be bumped on core version release.
    if not target.prerelease:
        if not is_core_version(new_version):
            print(f"[*] {file}: Skipped (not targeting a core version)")
            return None

    new_content = content
    startpos = 0
    while match := pattern.search(new_content, pos=startpos):
        version = match.groupdict()["version"]
        if version == current_version:
            start, end = match.span()
            new_span = new_content[start:end].replace(current_version, new_version)
            new_content = new_content[:start] + new_span + new_content[end:]
            startpos = end
        elif version == new_version:
            break
        else:
            raise ValueError(
                f"'{file}' contains invalid version: expected '{current_version}' but found '{version}'"
            )

    show_diff(content, new_content, file)

    return new_content


def show_diff(before: str, after: str, file: pathlib.Path):
    diffs = list(
        difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True), n=0
        )
    )[2:]
    print(f"[*] Diff of '{file}':\n")
    print("".join(diffs))


def parse_args():
    parser = argparse.ArgumentParser("Bump version strings in the Pyodide repository")
    parser.add_argument("--new-version", help="New version")
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't actually write anything"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare the current contents to the updated contents and fail if it would change anything",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.new_version is None:
        new_version = input("New version (e.g. 0.22.0, 0.22.0a0, 0.22.0.dev0): ")
    else:
        new_version = args.new_version

    if re.fullmatch(PYTHON_VERSION_REGEX, new_version) is None:
        raise ValueError(f"Invalid new version: {new_version}")

    new_version_py = new_version
    new_version_js = python_version_to_js_version(new_version)

    # We want to update files in all-or-nothing strategy,
    # so we keep the queue of update functions
    update_queue = []

    targets = itertools.chain(
        zip(PYTHON_TARGETS, [new_version_py] * len(PYTHON_TARGETS), strict=True),
        zip(JS_TARGETS, [new_version_js] * len(JS_TARGETS), strict=True),
    )
    for target, new_version in targets:
        current_version = parse_current_version(target)
        new_content = generate_updated_content(target, current_version, new_version)
        if new_content is not None:
            update_queue.append((target, new_content))

    if args.check:
        if update_queue:
            print("Version update would change files, failing", file=sys.stderr)
            return 1
        return 0
    if args.dry_run:
        return 0

    for target, content in update_queue:
        target.file.write_text(content)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
