import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parents[2]))

from pyodide_build.common import (
    _parse_package_subset,
    get_make_flag,
    get_make_environment_vars,
)  # noqa


def test_parse_package_subset():
    assert _parse_package_subset(None) is None
    # micropip is always included
    assert _parse_package_subset("numpy,pandas") == {
        "pyparsing",
        "packaging",
        "micropip",
        "numpy",
        "pandas",
    }

    # duplicates are removed
    assert _parse_package_subset("numpy,numpy") == {
        "pyparsing",
        "packaging",
        "micropip",
        "numpy",
    }

    # no empty package name included, spaces are handled
    assert _parse_package_subset("x,  a, b, c   ,,, d,,") == {
        "pyparsing",
        "packaging",
        "micropip",
        "x",
        "a",
        "b",
        "c",
        "d",
    }


def test_get_make_flag():
    assert len(get_make_flag("SIDE_MODULE_LDFLAGS")) > 0
    assert len(get_make_flag("SIDE_MODULE_CFLAGS")) > 0
    # n.b. right now CXXFLAGS is empty so don't check length here, just check it returns
    get_make_flag("SIDE_MODULE_CXXFLAGS")


def test_get_make_environment_vars():
    vars = get_make_environment_vars()
    assert "SIDE_MODULE_LDFLAGS" in vars
    assert "SIDE_MODULE_CFLAGS" in vars
    assert "SIDE_MODULE_CXXFLAGS" in vars
    assert "TOOLSDIR" in vars
