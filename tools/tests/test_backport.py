import sys
from copy import deepcopy
from pathlib import Path
from textwrap import dedent

sys.path.append(str(Path(__file__).parents[1]))
from backport import (
    Changelog,
    ChangelogEntry,
    ChangelogParagraph,
    ChangelogSection,
    ChangelogVersion,
    PrChangelogIndex,
)

TEST_CHANGELOG = dedent(
    """\
    # Change Log

    ## Unreleased

    - ABI break: Upgraded Emscripten to 3.1.63 {pr}`5343` {pr}`5350`
    - Added `jiter` 0.8.2 {pr}`5388`

    - {{ Fix }} `mountNativeFS` API now correctly propagates the error. {pr}`5434`
    - {{ Fix }} Since 0.27.1, Pyodide has been broken in iOS because iOS ships
    broken wasm-gc support. Pyodide feature detects whether the runtime supports
    wasm-gc and uses it if it is present. Unfortunately, iOS passes the feature
    detection but wasm-gc doesn't work as expected. {pr}`5445`

    ### Packages

    - Added `h3` 4.2.1 {pr}`5436`
    - Added `pcodec` 0.3.3 {pr}`5432`

    - {{ Breaking }} `matplotlib-pyodide` is not a default backend for matplotlib anymore.
    Users who want to use `matplotlib-pyodide` need to explicitly call
    `matplotlib.use("module://matplotlib_pyodide.wasm_backend")`.
    {pr}`5374`

    ## Version 0.27.2
    """
)


def make_entry(*lines):
    return ChangelogEntry(content=list(lines))


def make_paragraph(*entries):
    return ChangelogParagraph(entries=list(entries))


def get_expected_changelog():
    unlabeled = ChangelogSection(
        paragraphs=[
            make_paragraph(
                make_entry(
                    "- ABI break: Upgraded Emscripten to 3.1.63 {pr}`5343` {pr}`5350`",
                ),
                make_entry(
                    "- Added `jiter` 0.8.2 {pr}`5388`",
                ),
            ),
            make_paragraph(
                make_entry(
                    "- {{ Fix }} `mountNativeFS` API now correctly propagates the error. {pr}`5434`",
                ),
                make_entry(
                    "- {{ Fix }} Since 0.27.1, Pyodide has been broken in iOS because iOS ships",
                    "broken wasm-gc support. Pyodide feature detects whether the runtime supports",
                    "wasm-gc and uses it if it is present. Unfortunately, iOS passes the feature",
                    "detection but wasm-gc doesn't work as expected. {pr}`5445`",
                ),
            ),
        ],
    )
    packages = ChangelogSection(
        header=["### Packages", ""],
        paragraphs=[
            make_paragraph(
                make_entry(
                    "- Added `h3` 4.2.1 {pr}`5436`",
                ),
                make_entry(
                    "- Added `pcodec` 0.3.3 {pr}`5432`",
                ),
            ),
            make_paragraph(
                make_entry(
                    "- {{ Breaking }} `matplotlib-pyodide` is not a default backend for matplotlib anymore.",
                    "Users who want to use `matplotlib-pyodide` need to explicitly call",
                    '`matplotlib.use("module://matplotlib_pyodide.wasm_backend")`.',
                    "{pr}`5374`",
                ),
            ),
        ],
    )
    return Changelog(
        prelude=ChangelogVersion(header=["# Change Log", ""]),
        unreleased=ChangelogVersion(
            header=["## Unreleased", ""],
            sections=[unlabeled, packages],
        ),
        rest=ChangelogVersion(header=["## Version 0.27.2"]),
    )


def test_roundtrip():
    parsed = Changelog.from_text(TEST_CHANGELOG)
    assert parsed.get_text() == TEST_CHANGELOG


def test_parsed():
    parsed = Changelog.from_text(TEST_CHANGELOG)
    assert parsed == get_expected_changelog()


def test_unparse():
    changelog = get_expected_changelog()
    unreleased = changelog.unreleased
    [unlabeled, packages] = unreleased.sections
    assert unlabeled.paragraphs[0].entries[0].get_text() == dedent(
        """\
        - ABI break: Upgraded Emscripten to 3.1.63 {pr}`5343` {pr}`5350`
        """
    )
    assert unlabeled.paragraphs[0].get_text() == dedent(
        """\
        - ABI break: Upgraded Emscripten to 3.1.63 {pr}`5343` {pr}`5350`
        - Added `jiter` 0.8.2 {pr}`5388`

        """
    )
    assert unlabeled.get_text() == dedent(
        """\
        - ABI break: Upgraded Emscripten to 3.1.63 {pr}`5343` {pr}`5350`
        - Added `jiter` 0.8.2 {pr}`5388`

        - {{ Fix }} `mountNativeFS` API now correctly propagates the error. {pr}`5434`
        - {{ Fix }} Since 0.27.1, Pyodide has been broken in iOS because iOS ships
        broken wasm-gc support. Pyodide feature detects whether the runtime supports
        wasm-gc and uses it if it is present. Unfortunately, iOS passes the feature
        detection but wasm-gc doesn't work as expected. {pr}`5445`

        """
    )
    assert packages.get_text() == dedent(
        """\
        ### Packages

        - Added `h3` 4.2.1 {pr}`5436`
        - Added `pcodec` 0.3.3 {pr}`5432`

        - {{ Breaking }} `matplotlib-pyodide` is not a default backend for matplotlib anymore.
        Users who want to use `matplotlib-pyodide` need to explicitly call
        `matplotlib.use("module://matplotlib_pyodide.wasm_backend")`.
        {pr}`5374`

        """
    )


def test_pr_index():
    changelog = Changelog.from_text(TEST_CHANGELOG)
    unreleased = changelog.unreleased
    unreleased.create_pr_index()
    assert unreleased.pr_index == {
        5343: PrChangelogIndex(0, 0, 0, False),
        5350: PrChangelogIndex(0, 0, 0, False),
        5374: PrChangelogIndex(1, 1, 0, True),
        5388: PrChangelogIndex(0, 0, 1, True),
        5432: PrChangelogIndex(1, 0, 1, True),
        5434: PrChangelogIndex(0, 1, 0, True),
        5436: PrChangelogIndex(1, 0, 0, True),
        5445: PrChangelogIndex(0, 1, 1, True),
    }


def test_add_backported_entries():
    changelog = Changelog.from_text(TEST_CHANGELOG)
    changelog.unreleased.create_pr_index()
    changelog.set_patch_release_notes("0.27.3", [5388])
    assert changelog.patch_release.get_text() == dedent(
        """\
        ## Version 0.27.3

        _Insert Date Here_

        - Added `jiter` 0.8.2 {pr}`5388`

        """
    )
    changelog.set_patch_release_notes("0.27.3", [5436])
    assert changelog.patch_release.get_text() == dedent(
        """\
        ## Version 0.27.3

        _Insert Date Here_

        ### Packages

        - Added `h3` 4.2.1 {pr}`5436`

        """
    )
    changelog.set_patch_release_notes("0.27.3", [5436, 5432])
    assert changelog.patch_release.get_text() == dedent(
        """\
        ## Version 0.27.3

        _Insert Date Here_

        ### Packages

        - Added `h3` 4.2.1 {pr}`5436`
        - Added `pcodec` 0.3.3 {pr}`5432`

        """
    )
    changelog.set_patch_release_notes("0.27.3", [5432, 5436])
    assert changelog.patch_release.get_text() == dedent(
        """\
        ## Version 0.27.3

        _Insert Date Here_

        ### Packages

        - Added `h3` 4.2.1 {pr}`5436`
        - Added `pcodec` 0.3.3 {pr}`5432`

        """
    )
    changelog.set_patch_release_notes("0.27.3", [5388, 5434])
    assert changelog.patch_release.get_text() == dedent(
        """\
        ## Version 0.27.3

        _Insert Date Here_

        - Added `jiter` 0.8.2 {pr}`5388`

        - {{ Fix }} `mountNativeFS` API now correctly propagates the error. {pr}`5434`

        """
    )

    changelog.set_patch_release_notes("0.27.3", [5432, 5388, 5434, 5436])
    assert changelog.patch_release.get_text() == dedent(
        """\
        ## Version 0.27.3

        _Insert Date Here_

        - Added `jiter` 0.8.2 {pr}`5388`

        - {{ Fix }} `mountNativeFS` API now correctly propagates the error. {pr}`5434`

        ### Packages

        - Added `h3` 4.2.1 {pr}`5436`
        - Added `pcodec` 0.3.3 {pr}`5432`

        """
    )


def test_remove_backported_entries():
    orig_changelog = Changelog.from_text(TEST_CHANGELOG)
    orig_changelog.unreleased.create_pr_index()

    changelog = deepcopy(orig_changelog)
    changelog.remove_release_notes_from_unreleased_section([5374, 5445])
    assert changelog.unreleased.get_text() == dedent(
        """\
        ## Unreleased

        - ABI break: Upgraded Emscripten to 3.1.63 {pr}`5343` {pr}`5350`
        - Added `jiter` 0.8.2 {pr}`5388`

        - {{ Fix }} `mountNativeFS` API now correctly propagates the error. {pr}`5434`

        ### Packages

        - Added `h3` 4.2.1 {pr}`5436`
        - Added `pcodec` 0.3.3 {pr}`5432`

        """
    )

    changelog = deepcopy(orig_changelog)
    changelog.remove_release_notes_from_unreleased_section([5374, 5445, 5434])
    assert changelog.unreleased.get_text() == dedent(
        """\
        ## Unreleased

        - ABI break: Upgraded Emscripten to 3.1.63 {pr}`5343` {pr}`5350`
        - Added `jiter` 0.8.2 {pr}`5388`

        ### Packages

        - Added `h3` 4.2.1 {pr}`5436`
        - Added `pcodec` 0.3.3 {pr}`5432`

        """
    )
    changelog = deepcopy(orig_changelog)
    changelog.remove_release_notes_from_unreleased_section([5374, 5445, 5388])
    assert changelog.unreleased.get_text() == dedent(
        """\
        ## Unreleased

        - ABI break: Upgraded Emscripten to 3.1.63 {pr}`5343` {pr}`5350`

        - {{ Fix }} `mountNativeFS` API now correctly propagates the error. {pr}`5434`

        ### Packages

        - Added `h3` 4.2.1 {pr}`5436`
        - Added `pcodec` 0.3.3 {pr}`5432`

        """
    )
    changelog = deepcopy(orig_changelog)
    changelog.remove_release_notes_from_unreleased_section(
        [5374, 5445, 5388, 5343, 5434]
    )
    assert changelog.unreleased.get_text() == dedent(
        """\
        ## Unreleased

        ### Packages

        - Added `h3` 4.2.1 {pr}`5436`
        - Added `pcodec` 0.3.3 {pr}`5432`

        """
    )
    changelog = deepcopy(orig_changelog)
    changelog.remove_release_notes_from_unreleased_section(
        [5374, 5445, 5388, 5436, 5432]
    )
    assert changelog.unreleased.get_text() == dedent(
        """\
        ## Unreleased

        - ABI break: Upgraded Emscripten to 3.1.63 {pr}`5343` {pr}`5350`

        - {{ Fix }} `mountNativeFS` API now correctly propagates the error. {pr}`5434`

        """
    )
