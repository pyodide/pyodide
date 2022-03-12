from pyodide_build.common import (
    ALWAYS_PACKAGES,
    CORE_PACKAGES,
    CORE_SCIPY_PACKAGES,
    UNVENDORED_STDLIB_MODULES,
    _parse_package_subset,
    get_make_environment_vars,
    get_make_flag,
)


def test_parse_package_subset():
    assert (
        _parse_package_subset("numpy,pandas")
        == {
            "numpy",
            "pandas",
        }
        | UNVENDORED_STDLIB_MODULES
        | ALWAYS_PACKAGES
    )

    # duplicates are removed
    assert (
        _parse_package_subset("numpy,numpy")
        == {
            "numpy",
        }
        | UNVENDORED_STDLIB_MODULES
        | ALWAYS_PACKAGES
    )

    # no empty package name included, spaces are handled
    assert (
        _parse_package_subset("x,  a, b, c   ,,, d,,")
        == {
            "x",
            "a",
            "b",
            "c",
            "d",
        }
        | UNVENDORED_STDLIB_MODULES
        | ALWAYS_PACKAGES
    )

    assert (
        _parse_package_subset("core")
        == CORE_PACKAGES | UNVENDORED_STDLIB_MODULES | ALWAYS_PACKAGES
    )
    # by default core packages are built
    assert _parse_package_subset(None) == _parse_package_subset("core")

    assert (
        _parse_package_subset("min-scipy-stack")
        == CORE_SCIPY_PACKAGES
        | CORE_PACKAGES
        | UNVENDORED_STDLIB_MODULES
        | ALWAYS_PACKAGES
    )
    # reserved key words can be combined with other packages
    assert _parse_package_subset("core, unknown") == _parse_package_subset("core") | {
        "unknown"
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
