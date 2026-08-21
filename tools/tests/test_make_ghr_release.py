import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parents[1]))
from make_ghr_release import (
    changelog_anchor,
    ghr_args,
    is_prerelease,
    redact,
    release_body,
)

CHANGELOG = """\
# Change Log

## Version 314.0.3

_August 4, 2026_

- Something changed

## Version 0.29.4

- Something else changed
"""


@pytest.fixture
def changelog_path(tmp_path):
    path = tmp_path / "changelog.md"
    path.write_text(CHANGELOG)
    return path


@pytest.mark.parametrize(
    "tag, anchor",
    [
        ("314.0.3", "version-314-0-3"),
        ("0.29.4", "version-0-29-4"),
        ("314.0.4", "change-log"),
    ],
)
def test_changelog_anchor(changelog_path, tag, anchor):
    assert changelog_anchor(tag, changelog_path) == anchor


def test_changelog_anchor_no_changelog(tmp_path):
    assert changelog_anchor("314.0.3", tmp_path / "nope.md") == "change-log"


def test_release_body(changelog_path):
    assert release_body("314.0.3", changelog_path) == (
        "See changes at "
        "https://pyodide.org/en/stable/project/changelog.html#version-314-0-3"
    )


def test_release_body_prerelease(changelog_path):
    # Alphas aren't in the published docs, link to the repo at the tag
    assert release_body("314.0.0a1", changelog_path) == (
        "See changes at "
        "https://github.com/pyodide/pyodide/blob/314.0.0a1/docs/project/changelog.md#unreleased"
    )


def test_ghr_args(changelog_path):
    args = ghr_args(
        tag="314.0.3",
        dist_dir=Path("dist"),
        token="secret",
        owner="pyodide",
        repo="pyodide",
        commit="abc123",
        ghr_bin="/tmp/ghr-bin",
        changelog_path=changelog_path,
    )
    assert args == [
        "/tmp/ghr-bin",
        "-t",
        "secret",
        "-u",
        "pyodide",
        "-r",
        "pyodide",
        "-c",
        "abc123",
        "-b",
        "See changes at "
        "https://pyodide.org/en/stable/project/changelog.html#version-314-0-3",
        "-delete",
        "314.0.3",
        "dist",
    ]


def test_ghr_args_prerelease(changelog_path):
    args = ghr_args(
        tag="314.0.0a1",
        dist_dir=Path("dist"),
        token="secret",
        owner="pyodide",
        repo="pyodide",
        commit="abc123",
        ghr_bin="/tmp/ghr-bin",
        changelog_path=changelog_path,
    )
    assert args[-3:] == ["-prerelease", "314.0.0a1", "dist"]
    assert args[args.index("-b") + 1] == (
        "See changes at "
        "https://github.com/pyodide/pyodide/blob/314.0.0a1/docs/project/changelog.md#unreleased"
    )


def test_redact():
    assert redact(["ghr", "-t", "secret", "0.29.4"], "secret") == "ghr -t $GITHUB_TOKEN 0.29.4"


def test_changelog_anchor_current_changelog():
    # The real changelog should have a section for a released version
    assert changelog_anchor("314.0.3") == "version-314-0-3"
