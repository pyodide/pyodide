#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

"""
The main purpose of this script is to automate the changelog transformations
involved in backports. Many cherry-picks lead to changelog conflicts, and we
need also to rearrange the changelog on the main branch.

We implement a parser for the changelog to perform the transformations needed.
This is the most complicated part, since we want to maintain the ordering and
the structure while moving entries from one section to another.

There are also some miscellaneous utilities for adding or removing the "needs
backport" label and for showing which backport PRs are missing changelog
entries.
"""

import argparse
import functools
import os
import re
import subprocess
import sys
from collections import namedtuple
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Self

try:
    import argcomplete
except ImportError:
    argcomplete = None

TOOLS = Path(__file__).parent
PYODIDE_ROOT = TOOLS.parent
CHANGELOG = PYODIDE_ROOT / "docs/project/changelog.md"
INSERT_DATE_HERE = "Insert Date Here"


def run(
    args: list[str | Path], check: bool = True, **kwargs: Any
) -> subprocess.CompletedProcess[Any]:
    result = subprocess.run(args, check=False, text=True, **kwargs)
    if check and result.returncode:
        print(f"Command failed with exit status {result.returncode}")
        print("Command was:", " ".join(str(x) for x in args))
        sys.exit(result.returncode)
    return result


@functools.cache
def get_needs_backport_pr_numbers() -> tuple[int, ...]:
    """Use gh cli to collect the set of PRs that are labeled as needs_backport."""
    result = run(
        ["gh", "pr", "list", "--label", "needs backport", "--state", "closed"],
        capture_output=True,
    )
    lines = [line.split("\t", 1)[0] for line in result.stdout.splitlines()]
    return tuple(sorted(int(line) for line in lines))


@functools.cache
def get_needs_backport_prs_strings() -> tuple[str, ...]:
    return tuple(str(pr) for pr in get_needs_backport_pr_numbers())


#
# Commit log parsing
#

# we use history_idx to sort by age.
CommitInfo = namedtuple(
    "CommitInfo", ["pr_number", "shorthash", "shortlog", "history_idx"]
)


def commits_to_prs(commits: list[CommitInfo]) -> list[int]:
    return [c.pr_number for c in commits]


class CommitHistory:
    """Store the history of the github PRs with a map from pr_number to CommitInfo"""

    commits: dict[int, CommitInfo]

    @classmethod
    def from_git(self):
        result = run(["git", "log", "--oneline", "main"], capture_output=True)
        lines = result.stdout.splitlines()
        return CommitHistory(lines)

    def __init__(self, lines):
        commits = {}
        PR_NUMBER_RE = re.compile(r"\(#[0-9]+\)$")
        for history_idx, line in enumerate(lines):
            if not (m := PR_NUMBER_RE.search(line)):
                continue
            pr_number = int(m.group(0)[2:-1])
            shorthash, shortlog = line.split(" ", 1)
            commits[pr_number] = CommitInfo(pr_number, shorthash, shortlog, history_idx)

        self.commits = commits

    def lookup_pr(self, pr_number: int) -> CommitInfo:
        return self.commits[pr_number]


@functools.cache
def get_commits() -> list[CommitInfo]:
    """Return the CommitInfo of the PRs we want to backport"""
    pr_numbers = get_needs_backport_pr_numbers()
    commit_history = CommitHistory.from_git()
    commits = [commit_history.lookup_pr(x) for x in pr_numbers]
    return sorted(commits, key=lambda c: -c.history_idx)


#
# Changelog parsing
#
# See tests in tools/tests/test_backports.py.


@dataclass
class ChangelogEntry:
    """A changelog entry, represented as a list of strings.

    An entry is started by a line beginning with `-`. It ends when there is a
    line starting with `##` (begins a new version) `###` (begins a new
    subsection), a blank line (begins a new paragraph) or `-` (begins a new
    entry).

    This is nearly the same thing as its content.
    """

    content: list[str] = field(default_factory=list)

    def get_text(self) -> str:
        if self.content:
            return "\n".join(self.content) + "\n"
        return ""

    def __bool__(self) -> bool:
        return bool(self.content)

    def append(self, line: str) -> None:
        self.content.append(line)


@dataclass
class ChangelogParagraph:
    """A paragraph grouping of changelog entries separated by blank lines.

    Introduced by a line starting with a -. Ended by a blank line, or ### or ##.

    header:
        Probably empty?

    entries:
        The list of entries.

    cur_entry:
        Parser state.
    """

    header: list[str] = field(default_factory=list)
    entries: list[ChangelogEntry] = field(default_factory=list)
    cur_entry: ChangelogEntry = field(default_factory=ChangelogEntry)

    def get_text(self) -> str:
        """Unparse the paragraph"""
        header = ""
        if self.header:
            header = "\n".join(self.header) + "\n"
        res = header + "".join(x.get_text() for x in self.entries)
        # Special case: if the last entry already ends in a blank line, we don't
        # add another one. This keeps the spacing more consistent with the
        # backported entries.
        if not res.endswith("\n\n"):
            res += "\n"
        return res

    def __bool__(self) -> bool:
        return bool(self.header or self.entries or self.cur_entry)

    def append(self, line: str) -> None:
        """Main parsing logic."""
        if line.startswith("-"):
            self.finish_entry()
        if self.cur_entry or line.startswith("-"):
            self.cur_entry.append(line)
        else:
            self.header.append(line)

    def finish_entry(self) -> None:
        """If cur_entry is nonempty, add it to entries. Then empty out cur_entry"""
        if self.cur_entry:
            self.entries.append(self.cur_entry)
            self.cur_entry = ChangelogEntry()


@dataclass
class ChangelogSection:
    """A section of the changelog for a particular version of Pyodide

    Introduced by ### or ##. Ends when there is another line with ### or ##.

    header:
        Consists of all the lines starting with and the subsection start "###"
        line and including all content lines up untile the first line that
        starts with -. Generally this will be a heading like "### Packages" plus
        one or more empty lines. The first `ChangelogSection` in a
        `ChangelogVersion` may have an empty heading.

    paragraphs:
        The list of paragraphs.

    cur_paragraph:
        Parser state.
    """

    header: list[str] = field(default_factory=list)
    paragraphs: list[ChangelogParagraph] = field(default_factory=list)
    cur_paragraph: ChangelogParagraph = field(default_factory=ChangelogParagraph)

    def get_text(self) -> str:
        """Unparse the subsection"""
        header = ""
        if self.header:
            header = "\n".join(self.header) + "\n"
        res = header + "".join(x.get_text() for x in self.paragraphs)
        # Special case: if the last entry already ends in a blank line, we don't
        # add another one. This keeps the spacing more consistent with the
        # backported entries.
        if not res.endswith("\n\n"):
            res += "\n"
        return res

    def __bool__(self) -> bool:
        return bool(self.header or self.paragraphs or self.cur_paragraph)

    def append(self, line: str) -> None:
        """Main parsing logic."""
        if line.strip() == "":
            if self.cur_paragraph:
                self.finish_paragraph()
            else:
                self.header.append(line)
            return
        if self.cur_paragraph or line.startswith("-"):
            self.cur_paragraph.append(line)
        else:
            self.header.append(line)

    def finish_paragraph(self) -> None:
        """If cur_paragraph is nonempty, add it to entries. Then empty out cur_paragraph"""
        if self.cur_paragraph:
            self.cur_paragraph.finish_entry()
            self.paragraphs.append(self.cur_paragraph)
            self.cur_paragraph = ChangelogParagraph()


PrChangelogIndex = namedtuple(
    "PrChangelogIndex", ["subsection", "paragraph", "entry", "is_unique"]
)


@dataclass
class ChangelogVersion:
    """The changelog information for a particular release of Pyodide.

    Introduced by ##. Ends when there is a ##.

    header:
        Other than the unreleased section we don't actually bother parsing out
        the changelog. So for the "prelude" and "rest" sections, this is
        actually all the content.

        For the unreleased and patch_release sections, this is only the content
        up to the first entry or subsection. So that should include just the `##
        Unreleased` line and a blank line or two.

    sections:
        The list of sections.

    cur_section:
        Parser state.

    pr_index:
        For the unreleased section, we populate this with information about
        where the release note for each PR is. Populated by create_pr_index().
    """

    header: list[str] = field(default_factory=list)
    sections: list[ChangelogSection] = field(default_factory=list)
    cur_section: ChangelogSection = field(default_factory=ChangelogSection)
    pr_index: dict[int, PrChangelogIndex] = field(default_factory=dict)

    def get_text(self) -> str:
        """Unparse the section"""
        header = ""
        if self.header:
            header = "\n".join(self.header) + "\n"
        return header + "".join(x.get_text() for x in self.sections)

    def append(self, line: str) -> None:
        """Main parsing logic."""
        if line.startswith("### "):
            self.finish_section()
        if self.cur_section or line.startswith(("-", "### ")):
            self.cur_section.append(line)
        else:
            self.header.append(line)

    def append_lines(self, lines: list[str]) -> None:
        for line in lines:
            self.append(line)

    def finish_section(self) -> None:
        """If cur_section is nonempty, add it to entries. Then empty out cur_entry"""
        if self.cur_section:
            self.cur_section.finish_paragraph()
            self.sections.append(self.cur_section)
            self.cur_section = ChangelogSection()

    def create_pr_index(self) -> None:
        PR_NUMBER_RE = re.compile(r"{pr}`[0-9]+`")
        for subsection_idx, subsection in enumerate(self.sections):
            for paragraph_idx, paragraph in enumerate(subsection.paragraphs):
                for entry_idx, entry in enumerate(paragraph.entries):
                    pr_strs = PR_NUMBER_RE.findall(entry.get_text())
                    is_unique = len(pr_strs) == 1
                    for pr_str in pr_strs:
                        pr = int(pr_str[5:-1])
                        self.pr_index[pr] = PrChangelogIndex(
                            subsection_idx, paragraph_idx, entry_idx, is_unique
                        )

    def delete_entry(self, pr_changelog_index: PrChangelogIndex) -> None:
        subsection = self.sections[pr_changelog_index.subsection]
        paragraph = subsection.paragraphs[pr_changelog_index.paragraph]
        del paragraph.entries[pr_changelog_index.entry]
        if not paragraph.entries:
            del subsection.paragraphs[pr_changelog_index.paragraph]
        if not subsection.paragraphs:
            del self.sections[pr_changelog_index.subsection]


@dataclass
class Changelog:
    """Class for keeping track of an item in inventory."""

    file: Path | None = None
    prelude: ChangelogVersion = field(default_factory=ChangelogVersion)
    unreleased: ChangelogVersion = field(default_factory=ChangelogVersion)
    patch_release: ChangelogVersion = field(default_factory=ChangelogVersion)
    rest: ChangelogVersion = field(default_factory=ChangelogVersion)

    @classmethod
    def from_file(cls, file):
        return Changelog(file).parse(file.read_text())

    @classmethod
    def from_text(cls, text):
        return Changelog().parse(text)

    def parse(self, changelog_text: str) -> Self:
        changelog = changelog_text.splitlines()

        it = iter(changelog)
        for line in it:
            if line.startswith("## Unreleased"):
                self.unreleased.header.append(line)
                break
            # We don't care what's in the prelude so it all goes in the header
            self.prelude.header.append(line)
        # Parse unreleased section
        for line in it:
            if line.startswith("## "):
                self.unreleased.finish_section()
                self.rest.header.append(line)
                break
            self.unreleased.append(line)

        # We don't care what's in the rest so it all goes in the header
        self.rest.header.extend(it)
        return self

    def get_text(self, include_unreleased=True):
        # For the backports changelog we want to drop the unreleased section
        # entirely.
        unreleased = self.unreleased.get_text() if include_unreleased else ""
        return (
            self.prelude.get_text()
            + unreleased
            + self.patch_release.get_text()
            + self.rest.get_text()
        )

    def write_text(self, include_unreleased=True):
        assert self.file
        self.file.write_text(self.get_text(include_unreleased=include_unreleased))

    def set_patch_release_notes(
        self, version: str, pr_numbers: list[int], date: str = "Insert Date Here"
    ) -> None:
        """Given a list of PRs, check if they have a changelog entry in
        "Unreleased".

        If so add the entry to the patch_release section. Don't remove the entry
        from the unreleased section, just duplicate it.
        """
        self.patch_release = ChangelogVersion()
        self.patch_release.append_lines([f"## Version {version}", "", f"_{date}_", ""])
        backport_subsections = {}
        backport_subsubsections = {}

        # Sort by order of appearance then add
        changelog_indices = [
            pr_index
            for pr_number in pr_numbers
            if (pr_index := self.unreleased.pr_index.get(pr_number, None))
        ]

        changelog_indices = sorted(
            changelog_indices,
            key=lambda idx: (idx.subsection, idx.paragraph, idx.entry),
        )
        for pr_index in changelog_indices:
            subsection = self.unreleased.sections[pr_index.subsection]
            if pr_index.subsection in backport_subsections:
                backport_subsection = backport_subsections[pr_index.subsection]
            else:
                backport_subsection = deepcopy(subsection)
                backport_subsection.paragraphs = []
                backport_subsections[pr_index.subsection] = backport_subsection
                self.patch_release.sections.append(backport_subsection)

            paragraph = subsection.paragraphs[pr_index.paragraph]
            subsub_index = (pr_index.subsection, pr_index.paragraph)
            if subsub_index in backport_subsubsections:
                backport_subsubsection = backport_subsubsections[subsub_index]
            else:
                backport_subsubsection = deepcopy(paragraph)
                backport_subsubsection.entries = []
                backport_subsubsections[subsub_index] = backport_subsubsection
                backport_subsection.paragraphs.append(backport_subsubsection)

            entry = paragraph.entries[pr_index.entry]
            backport_subsubsection.entries.append(entry)

    def remove_release_notes_from_unreleased_section(
        self, pr_numbers: list[int]
    ) -> None:
        # Have to do this in two passes:
        # 1. collect up entries to delete
        indices_to_delete = [
            pr_index
            for pr_number in pr_numbers
            if (pr_index := self.unreleased.pr_index.get(pr_number, None))
        ]

        # 2. Sort by reverse order of appearance and then delete.
        for idx in sorted(
            indices_to_delete,
            key=lambda idx: (-idx.subsection, -idx.paragraph, -idx.entry),
        ):
            self.unreleased.delete_entry(idx)


#
# Some helpers
#


def today():
    return datetime.today().strftime("%B %d, %Y")


def branch_exists(branch_name: str) -> bool:
    res = run(["git", "branch", "--list", branch_name], capture_output=True)
    return bool(res.stdout.strip())


def update_old_branch(branch_name):
    branch_name_old = branch_name + "-old"
    run(["git", "branch", "-f", branch_name_old, branch_name])


def force_branch_update(branch_name):
    branch_already_exists = branch_exists(branch_name)
    if branch_already_exists:
        update_old_branch(branch_name)
    run(["git", "switch", "-C", branch_name])


def diff_old_new_branch(branch_name):
    branch_name_old = branch_name + "-old"
    if not branch_exists(branch_name_old):
        return
    if os.isatty(sys.stdout.fileno()):
        print("\nWill show diff between previous branch and new branch.")
        input("Press enter to continue.")
    run(["git", "diff", branch_name_old, branch_name])


def get_version() -> str:
    result = run(["git", "tag"], capture_output=True)
    (major, minor, patch) = max(
        tuple(int(p) for p in x.split("."))
        for x in result.stdout.splitlines()
        if x.startswith("0") and "a" not in x
    )
    patch += 1
    return f"{major}.{minor}.{patch}"


#
# Main commands
#


def add_backport_pr(args):
    for pr_number in args.pr_numbers:
        run(
            [
                "gh",
                "pr",
                "edit",
                pr_number,
                "--add-label",
                "needs backport",
            ]
        )


def clear_backport_prs(args) -> None:
    needs_backport_prs = get_needs_backport_prs_strings()
    print("Removing the needs-backport label from the following PRs:")
    print("  ", ", ".join(needs_backport_prs), "\n")
    if not args.yes:
        input("Press enter to continue")
    for pr_number in needs_backport_prs:
        run(["gh", "pr", "edit", str(pr_number), "--remove-label", "needs backport"])
    print("To reverse this, run")
    print(f"  ./tools/backport.py add-backport-pr {' '.join(needs_backport_prs)}")


def show_missing_changelogs(args) -> None:
    changelog = Changelog.from_file(CHANGELOG)
    changelog.unreleased.create_pr_index()
    commits = get_commits()
    missing_changelogs = [
        commit
        for commit in commits
        if commit.pr_number not in changelog.unreleased.pr_index
    ]
    for commit in missing_changelogs:
        if args.web:
            run(["gh", "pr", "view", "-w", str(commit.pr_number)])
        else:
            print(commit.pr_number, commit.shorthash, commit.shortlog)


def make_changelog_branch(args) -> None:
    commits = get_commits()
    prs = commits_to_prs(commits)
    version = get_version()
    run(["git", "fetch", "upstream", "main:main", "--update-head-ok", "--force"])
    run(["git", "switch", "main"])
    changelog = Changelog.from_file(CHANGELOG)
    changelog.unreleased.create_pr_index()
    branch_name = f"changelog-for-{version}"
    force_branch_update(branch_name)
    changelog.set_patch_release_notes(version, prs, INSERT_DATE_HERE)
    changelog.remove_release_notes_from_unreleased_section(prs)
    changelog.write_text()
    run(["git", "add", CHANGELOG])
    run(["git", "commit", "-m", f"Update changelog for v{version}"])
    diff_old_new_branch(branch_name)


def make_backport_branch(args) -> None:
    """
    To make the backport branch, first we query the set of PRs that are tagged with
    'needs-backport'. Then we sort them in chronological order by date merged.
    (This was annoying to do manually -- the github interface lets you sort PRs
    by creation date or last modified date but not by merge date).

    Then we cherry-pick each commit in order by merge date but also render the change log
    automatically. If the cherry-pick succeeds, we write out the new change log and amend
    the commit. If it fails, we write out the change log and add it. We also check if
    pyodide-build is in conflict and if so I take the new `pyodide-build` commit that.
    Then we try `git cherry-pick --continue`. If it still fails, we abort and ask the user
    to resolve conflicts manually, run `git cherry-pick --continue` and then rerun the script.
    For this to work, we need to set `rerere.enabled` and `rerere.autoupdate`.
    """
    commits = get_commits()
    version = get_version()
    run(["git", "fetch", "upstream", "main:main", "--update-head-ok", "--force"])
    run(["git", "fetch", "upstream", "stable:stable", "--update-head-ok", "--force"])
    run(["git", "config", "rerere.enabled", "true"])
    run(["git", "config", "rerere.autoupdate", "true"])
    run(["git", "switch", "main"])
    changelog = Changelog.from_file(CHANGELOG)
    changelog.unreleased.create_pr_index()
    run(["git", "switch", "stable"])
    run(["git", "submodule", "update"])
    branch_name = f"backports-for-{version}"
    force_branch_update(branch_name)
    for n, cur_commit in enumerate(commits):
        result = run(
            ["git", "-c", "core.editor=true", "cherry-pick", cur_commit.shorthash],
            check=False,
            capture_output=True,
        )
        for line in result.stdout.splitlines():
            # We need to resolve submodule conflicts ourselves. We always pick
            # the submodule version from the commit we are cherry-picking.
            if not line.startswith("CONFLICT (submodule)"):
                continue
            path = line.partition("Merge conflict in ")[-1]
            run(
                ["git", "checkout", cur_commit.shorthash, "--", path],
                capture_output=True,
            )
        changelog.set_patch_release_notes(
            version, commits_to_prs(commits[: n + 1]), INSERT_DATE_HERE
        )
        changelog.write_text(include_unreleased=False)
        run(["git", "add", "docs/project/changelog.md"])
        if result.returncode == 0:
            run(["git", "commit", "--amend"])
        else:
            result2 = run(
                ["git", "cherry-pick", "--continue", "--no-edit"], check=False
            )
            if result2.returncode:
                print("\n\n")
                print("\033[1;33mCherry-pick failed:\033[m")
                print("  ", cur_commit.shortlog)
                print(
                    "Resolve conflicts and run `git cherry-pick --continue` then rerun."
                )
                sys.exit(result2.returncode)

    diff_old_new_branch(branch_name)


def open_release_prs(args):
    version = get_version()
    INSERT_ACTUAL_DATE = "- [ ] Insert the actual date in the changelog\n"
    MERGE_DONT_SQUASH = "- [ ] Merge, don't squash"
    BACKPORTS_BRANCH = f"backports-for-{version}"
    CHANGELOG_BRANCH = f"changelog-for-{version}"

    run(["git", "switch", BACKPORTS_BRANCH])
    run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            "stable",
            "--title",
            f"Backports for v{version}",
            "--body",
            INSERT_ACTUAL_DATE + MERGE_DONT_SQUASH,
            "--web",
        ]
    )

    run(["git", "switch", CHANGELOG_BRANCH])
    run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            "main",
            "--title",
            f"Changelog for v{version}",
            "--body",
            INSERT_ACTUAL_DATE,
            "--web",
        ]
    )


def set_date(args):
    version = get_version()
    BACKPORTS_BRANCH = f"backports-for-{version}"
    CHANGELOG_BRANCH = f"changelog-for-{version}"
    update_old_branch(BACKPORTS_BRANCH)
    run(["git", "switch", BACKPORTS_BRANCH])
    run(
        [
            "git",
            "rebase",
            "stable",
            "--exec",
            " && ".join(
                [
                    f"sed -i 's/_{INSERT_DATE_HERE}_/_{today()}_/' docs/project/changelog.md",
                    "git add docs/project/changelog.md",
                    "git commit --amend --no-edit",
                ]
            ),
        ]
    )

    update_old_branch(CHANGELOG_BRANCH)
    run(["git", "switch", CHANGELOG_BRANCH])
    CHANGELOG.write_text(CHANGELOG.read_text().replace(INSERT_DATE_HERE, today()))
    run(["git", "add", "docs/project/changelog.md"])
    run(["git", "commit", "--amend", "--no-edit"])


def bump_version(args):
    version = get_version()
    extra_args = []
    if args.tag:
        extra_args += "--tag"

    run([TOOLS / "bump_version.py", version] + extra_args)


def parse_args():
    parser = argparse.ArgumentParser("Apply backports")
    parser.set_defaults(func=lambda args: parser.print_help())
    subparsers = parser.add_subparsers()

    add_backport_parser = subparsers.add_parser(
        "add-pr", help="Add the needs-backport label to a PR"
    )
    add_backport_parser.add_argument("pr_numbers", nargs="+", action="extend")
    add_backport_parser.set_defaults(func=add_backport_pr)

    clear_backport_prs_parser = subparsers.add_parser(
        "clear-prs",
        help="Remove the needs-backport label from all PRs with the label",
    )
    clear_backport_prs_parser.add_argument(
        "-y", "--yes", action="store_true", help="Don't prompt for whether to continue"
    )
    clear_backport_prs_parser.set_defaults(func=clear_backport_prs)

    missing_changelogs_parser = subparsers.add_parser(
        "missing-changelogs",
        help="List the PRs labeled as 'needs backport' that don't have a changelog",
    )
    missing_changelogs_parser.add_argument(
        "-w", "--web", action="store_true", help="Open missing changelog prs in browser"
    )
    missing_changelogs_parser.set_defaults(func=show_missing_changelogs)

    changelog_branch_parse = subparsers.add_parser(
        "changelog-branch", help="Make changelog-for-version branch"
    )
    changelog_branch_parse.set_defaults(func=make_changelog_branch)

    backport_branch_parse = subparsers.add_parser(
        "backport-branch", help="Make backports-for-version branch"
    )
    backport_branch_parse.set_defaults(func=make_backport_branch)

    open_release_prs_parse = subparsers.add_parser(
        "open-release-prs", help="Open PRs for the backports and changelog branches"
    )
    open_release_prs_parse.set_defaults(func=open_release_prs)

    set_date_parse = subparsers.add_parser(
        "set-date", help="Set the date in the changelog"
    )
    set_date_parse.set_defaults(func=set_date)

    bump_version_parser = subparsers.add_parser(
        "bump-version", help="Set the date in the changelog"
    )
    bump_version_parser.add_argument(
        "--tag",
        action="store_true",
        help="Commit and tag the result",
    )
    bump_version_parser.set_defaults(func=bump_version)

    if argcomplete:
        argcomplete.autocomplete(parser)
    return parser.parse_args()


def main():
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
