from pyodide_build.io import check_package_config


def test_wheel_and_host_deps():
    """Check that when source URL is a wheel

    there can be no host dependencies"""

    errors = check_package_config(
        {"source": {"url": "test.whl"}, "requirements": {"host": ["a"]}},
        raise_errors=False,
    )
    assert (
        "When source -> url is a wheel (test.whl) the package cannot have "
        "host dependencies. Found ['a']'"
    ) in errors
