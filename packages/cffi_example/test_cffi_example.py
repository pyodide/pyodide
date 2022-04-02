import pytest

from pyodide_build.testing import run_in_pyodide

CHROME_FAIL_v90_MSG = (
    "Doesn't work in chrome v89 or v90, I think because of "
    "https://bugs.chromium.org/p/chromium/issues/detail?id=1200031. "
    "Confirmed locally to work in v91 and v96, and to break on v90."
)


@pytest.mark.parametrize(
    "pattern,name,flags,expected",
    [
        ("foo", "bar", 0, False),
        ("f*", "foo", 0, True),
        ("f*bar", "f/bar", 0, True),
        ("f*bar", "f/bar", "fnmatch.FNM_PATHNAME", False),
    ],
)
def test_fnmatch(selenium_module_scope, pattern, name, flags, expected):
    selenium = selenium_module_scope
    if selenium.browser == "chrome":
        pytest.xfail(CHROME_FAIL_v90_MSG)
    selenium.load_package("cffi_example")
    result = selenium.run(
        f"""
        from cffi_example import fnmatch
        fnmatch.fnmatch({pattern!r}, {name!r}, {flags})
        """
    )
    assert result == expected


@run_in_pyodide(
    packages=["cffi_example"],
    module_scope=True,
    xfail_browsers={"chrome": CHROME_FAIL_v90_MSG},
)
def test_person():
    from cffi_example.person import Person

    p = Person("Alex", "Smith", 72)
    assert p.get_age() == 72
    assert p.get_full_name() == "Alex Smith"

    p = Person("x" * 100, "y" * 100, 72)
    assert p.get_full_name() == "x" * 100
