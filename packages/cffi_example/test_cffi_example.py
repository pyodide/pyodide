import pytest
from pytest_pyodide import run_in_pyodide


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
)
def test_person(selenium_module_scope):
    from cffi_example.person import Person

    p = Person("Alex", "Smith", 72)
    assert p.get_age() == 72
    assert p.get_full_name() == "Alex Smith"

    p = Person("x" * 100, "y" * 100, 72)
    assert p.get_full_name() == "x" * 100
