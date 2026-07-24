import io
import sys
from pathlib import Path

import ruamel.yaml

sys.path.append(str(Path(__file__).parents[1]))
from make_test_list import get_test_name, update_tests

yaml = ruamel.yaml.YAML()


def load(src: str):
    return yaml.load(src)


def dump(doc) -> str:
    buf = io.StringIO()
    yaml.dump(doc, buf)
    return buf.getvalue()


def names(doc) -> list[str]:
    return [get_test_name(item) for item in doc]


def test_update_tests_idempotent():
    """A list that already matches the tests, sorted, is left unchanged."""
    src = """\
- test_abc
- test_array
- test_zlib
"""
    doc = load(src)
    update_tests(doc, {"test_abc", "test_array", "test_zlib"})
    assert dump(doc) == src


def test_update_tests_adds_and_removes():
    doc = load("- test_abc\n- test_gone\n")
    update_tests(doc, {"test_abc", "test_new"})
    assert names(doc) == ["test_abc", "test_new"]


def test_update_tests_preserves_annotations():
    """Existing xfail/skip annotations are carried over, matched by name."""
    src = """\
- test_abc
- test_os:
    skip:
    # os.umask is not supported
    - test_mode
"""
    doc = load(src)
    update_tests(doc, {"test_abc", "test_os", "test_zlib"})
    assert names(doc) == ["test_abc", "test_os", "test_zlib"]
    out = dump(doc)
    assert "skip:" in out
    assert "# os.umask is not supported" in out
    assert "- test_mode" in out


def test_update_tests_preserves_header_comment():
    src = """\
# This is a header comment.
# It should survive the round-trip.

- test_abc
"""
    doc = load(src)
    update_tests(doc, {"test_abc"})
    out = dump(doc)
    assert "# This is a header comment." in out
    assert "# It should survive the round-trip." in out


def test_update_tests_sorts_out_of_order_entry():
    """An out-of-order entry gets sorted without duplicating anything.

    Regression test for a bug where the positional merge would insert the
    entire freshly-sorted list ahead of the old content as soon as a single
    entry was out of alphabetical order, duplicating every following entry.
    """
    # test_android is out of order (it sits after test_annotationlib) and is
    # annotated, exactly the shape that triggered the original bug.
    src = """\
- test_abc
- test_annotationlib
- test_android:
    xfail: platform-specific
- test_array
"""
    doc = load(src)
    tests = {"test_abc", "test_annotationlib", "test_android", "test_array"}
    update_tests(doc, tests)

    assert names(doc) == sorted(tests)
    # No duplicates, and the annotation moved with its entry.
    assert len(doc) == len(tests)
    out = dump(doc)
    assert out.count("xfail: platform-specific") == 1


def test_update_tests_dedupes_duplicated_block():
    """A file that already contains duplicated blocks is collapsed.

    Regression test for the duplicated-block corruption: a bare copy and an
    annotated copy of the same test collapse into a single annotated entry.
    """
    src = """\
- test_abc
- test_android:
    xfail: platform-specific
- test_os:
    skip:
    - test_mode
- test_abc
- test_android
- test_os
"""
    doc = load(src)
    tests = {"test_abc", "test_android", "test_os"}
    update_tests(doc, tests)

    assert names(doc) == sorted(tests)
    assert len(doc) == len(tests)
    out = dump(doc)
    # The annotated versions are the ones that are kept.
    assert out.count("xfail: platform-specific") == 1
    assert out.count("- test_mode") == 1
