import pytest
import shutil
from pathlib import Path


@pytest.mark.parametrize("active_server", ["main", "secondary"])
def test_load_from_url(selenium_standalone, web_server_secondary, active_server):

    if active_server == "secondary":
        url, port, log_main = web_server_secondary
        log_backup = selenium_standalone.server_log
    elif active_server == "main":
        _, _, log_backup = web_server_secondary
        log_main = selenium_standalone.server_log
        url = selenium_standalone.server_hostname
        port = selenium_standalone.server_port
    else:
        raise AssertionError()

    with log_backup.open("r") as fh_backup, log_main.open("r") as fh_main:

        # skip existing log lines
        fh_main.seek(0, 2)
        fh_backup.seek(0, 2)

        selenium_standalone.load_package(f"http://{url}:{port}/pyparsing.js")
        assert "Skipping unknown package" not in selenium_standalone.logs

        # check that all ressources were loaded from the active server
        txt = fh_main.read()
        assert '"GET /pyparsing.js HTTP/1.1" 200' in txt
        assert '"GET /pyparsing.data HTTP/1.1" 200' in txt

        # no additional ressources were loaded from the other server
        assert len(fh_backup.read()) == 0

    selenium_standalone.run(
        """
        from pyparsing import Word, alphas
        repr(Word(alphas).parseString('hello'))
        """
    )

    selenium_standalone.load_package(f"http://{url}:{port}/pytz.js")
    selenium_standalone.run("import pytz")


def test_load_relative_url(selenium_standalone):
    selenium_standalone.load_package("./pytz.js")
    selenium_standalone.run("import pytz")


def test_list_loaded_urls(selenium_standalone):
    selenium = selenium_standalone

    selenium.load_package("pyparsing")
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == [
        "pyparsing"
    ]
    assert (
        selenium.run_js("return pyodide.loadedPackages['pyparsing']")
        == "default channel"
    )


def test_uri_mismatch(selenium_standalone):
    selenium_standalone.load_package("pyparsing")
    selenium_standalone.load_package("http://some_url/pyparsing.js")
    assert (
        "URI mismatch, attempting to load package pyparsing" in selenium_standalone.logs
    )


def test_invalid_package_name(selenium):
    selenium.load_package("wrong name+$")
    assert "Skipping unknown package" in selenium.logs

    selenium.clean_logs()

    selenium.load_package("tcp://some_url")
    assert "Skipping unknown package" in selenium.logs


@pytest.mark.parametrize(
    "packages", [["pyparsing", "pytz"], ["pyparsing", "packaging"]], ids="-".join
)
def test_load_packages_multiple(selenium_standalone, packages):
    selenium = selenium_standalone
    selenium.load_package(packages)
    selenium.run(f"import {packages[0]}")
    selenium.run(f"import {packages[1]}")
    # The log must show that each package is loaded exactly once,
    # including when one package is a dependency of the other
    # ('pyparsing' and 'packaging')
    assert selenium.logs.count(f"Loading {packages[0]} from") == 1
    assert selenium.logs.count(f"Loading {packages[1]} from") == 1


@pytest.mark.parametrize(
    "packages", [["pyparsing", "pytz"], ["pyparsing", "packaging"]], ids="-".join
)
def test_load_packages_sequential(selenium_standalone, packages):
    selenium = selenium_standalone
    promises = ",".join('pyodide.loadPackage("{}")'.format(x) for x in packages)
    selenium.run_js("return Promise.all([{}])".format(promises))
    selenium.run(f"import {packages[0]}")
    selenium.run(f"import {packages[1]}")
    # The log must show that each package is loaded exactly once,
    # including when one package is a dependency of the other
    # ('pyparsing' and 'matplotlib')
    assert selenium.logs.count(f"Loading {packages[0]} from") == 1
    assert selenium.logs.count(f"Loading {packages[1]} from") == 1


def test_load_handle_failure(selenium_standalone):
    selenium = selenium_standalone
    selenium.load_package("pytz")
    selenium.run("import pytz")
    selenium.load_package("pytz2")
    selenium.load_package("pyparsing")
    assert "Loading pytz" in selenium.logs
    assert "Skipping unknown package 'pytz2'" in selenium.logs
    assert "Loading pyparsing" in selenium.logs


def test_load_failure_retry(selenium_standalone):
    """Check that a package can be loaded after failing to load previously"""
    selenium = selenium_standalone
    selenium.load_package("http://invalidurl/pytz.js")
    assert selenium.logs.count("Loading pytz from") == 1
    assert selenium.logs.count("Couldn't load package from URL") == 1
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == []

    selenium.load_package("pytz")
    selenium.run("import pytz")
    assert selenium.logs.count("Loading pytz from") == 2
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == ["pytz"]


def test_load_package_unknown(selenium_standalone):
    url = selenium_standalone.server_hostname
    port = selenium_standalone.server_port

    build_dir = Path(__file__).parents[2] / "build"
    shutil.copyfile(build_dir / "pyparsing.js", build_dir / "pyparsing-custom.js")
    shutil.copyfile(build_dir / "pyparsing.data", build_dir / "pyparsing-custom.data")

    try:
        selenium_standalone.load_package(f"http://{url}:{port}/pyparsing-custom.js")
    finally:
        (build_dir / "pyparsing-custom.js").unlink()
        (build_dir / "pyparsing-custom.data").unlink()

    assert selenium_standalone.run_js(
        "return window.pyodide.loadedPackages.hasOwnProperty('pyparsing-custom')"
    )


def test_load_twice(selenium_standalone):
    selenium_standalone.load_package("pytz")
    selenium_standalone.load_package("pytz")
    assert "pytz already loaded from default channel" in selenium_standalone.logs


def test_load_twice_different_source(selenium_standalone):
    selenium_standalone.load_package(["https://foo/pytz.js", "https://bar/pytz.js"])
    assert (
        "Loading same package pytz from https://bar/pytz.js and https://foo/pytz.js"
        in selenium_standalone.logs
    )


def test_load_twice_same_source(selenium_standalone):
    selenium_standalone.load_package(["https://foo/pytz.js", "https://foo/pytz.js"])
    assert "Loading same package pytz" not in selenium_standalone.logs


def test_js_load_package_from_python(selenium_standalone):
    selenium = selenium_standalone
    to_load = "pyparsing"
    selenium.run(f"import js ; js.pyodide.loadPackage(['{to_load}'])")
    assert f"Loading {to_load}" in selenium.logs
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == [to_load]


@pytest.mark.parametrize("jinja2", ["jinja2", "Jinja2"])
def test_load_package_mixed_case(selenium_standalone, jinja2):
    selenium = selenium_standalone
    selenium.run_js(
        f"""
        await pyodide.loadPackage("{jinja2}");
        pyodide.runPython(`
            import jinja2
        `)
        """
    )
