import pytest


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
    selenium.run(
        """
        from pyodide import package_loader
        from pyodide.package_loader import pyfetch, SITE_PACKAGES
        async def bad_load_package(url, name):
            resp = await pyfetch(url + "garbage")
            await resp.unpack_archive(extract_dir=SITE_PACKAGES)
            return to_js(list((SITE_PACKAGES / name).glob("**/*.so")))
        orig_load_package = package_loader.load_package
        package_loader.load_package = bad_load_package
        """
    )
    selenium.load_package("pytz")
    assert (
        selenium.logs.count(
            "OSError: Request for ./pytz-2021.1-py3-none-any.whlgarbage failed with status 404: File not found"
        )
        == 1
    )
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == []
    selenium.run("package_loader.load_package = orig_load_package")

    selenium.load_package("pytz")
    selenium.run("import pytz")
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == ["pytz"]


def test_load_twice(selenium_standalone):
    selenium_standalone.load_package("pytz")
    selenium_standalone.load_package("pytz")
    assert "No new packages to load" in selenium_standalone.logs


def test_js_load_package_from_python(selenium_standalone):
    selenium = selenium_standalone
    to_load = ["pyparsing"]
    selenium.run_js(
        f"""
        await pyodide.runPythonAsync(`
            from pyodide_js import loadPackage
            await loadPackage({to_load!r})
            del loadPackage
        `);
        """
    )
    assert f"Loading {to_load[0]}" in selenium.logs
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == to_load


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


def test_test_unvendoring(selenium_standalone):
    selenium = selenium_standalone
    selenium.run_js(
        """
        await pyodide.loadPackage("regex");
        pyodide.runPython(`
            import regex
            from pathlib import Path
            test_path =  Path(regex.__file__).parent / "test_regex.py"
            assert not test_path.exists()
        `)
        """
    )

    selenium.run_js(
        """
        await pyodide.loadPackage("regex-tests");
        pyodide.runPython(`
            assert test_path.exists()
        `)
        """
    )

    assert selenium.run_js(
        """
        return pyodide._module.packages['regex'].unvendored_tests
        """
    )
