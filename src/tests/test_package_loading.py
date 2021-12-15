import pytest
from pathlib import Path
import shutil

from conftest import JavascriptException


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
    assert selenium.logs.count(f"Loaded {packages[0]}, {packages[1]}") == 1


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
    assert selenium.logs.count(f"Loaded {packages[0]}") == 1
    assert selenium.logs.count(f"Loaded {packages[1]}") == 1


def test_load_handle_failure(selenium_standalone):
    selenium = selenium_standalone
    selenium.load_package("pytz")
    selenium.run("import pytz")
    with pytest.raises(JavascriptException, match="No known package with name pytz2"):
        selenium.load_package("pytz2")
    selenium.load_package("pyparsing")
    assert "Loaded pytz" in selenium.logs
    assert "Loaded pyparsing" in selenium.logs


@pytest.mark.skip_refcount_check
def test_load_failure_retry(selenium_standalone):
    """Check that a package can be loaded after failing to load previously"""
    selenium = selenium_standalone
    selenium.run_js(
        """
        self.orig_pytz_name = pyodide._module.packages["pytz"].file_name;
        pyodide._module.packages["pytz"].file_name += "garbage";
        """
    )
    selenium.load_package("pytz")
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == []
    selenium.run_js(
        """pyodide._module.packages["pytz"].file_name = self.orig_pytz_name"""
    )
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
    assert f"Loaded {to_load[0]}" in selenium.logs
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
        `);
        """
    )

    selenium.run_js(
        """
        await pyodide.loadPackage("regex-tests");
        pyodide.runPython(`
            assert test_path.exists()
        `);
        """
    )

    assert selenium.run_js(
        """
        return pyodide._module.packages['regex'].unvendored_tests;
        """
    )


def test_install_archive(selenium):
    build_dir = Path(__file__).parents[2] / "build"
    test_dir = Path(__file__).parent
    shutil.make_archive(
        test_dir / "test_pkg", "gztar", root_dir=test_dir, base_dir="test_pkg"
    )
    build_test_pkg = build_dir / "test_pkg.tar.gz"
    if not build_test_pkg.exists():
        build_test_pkg.symlink_to((test_dir / "test_pkg.tar.gz").absolute())
    try:
        for fmt_name in ["gztar", "tar.gz", "tgz", ".tar.gz", ".tgz"]:
            selenium.run_js(
                f"""
                let resp = await fetch("test_pkg.tar.gz");
                let buf = await resp.arrayBuffer();
                pyodide.unpackArchive(buf, {fmt_name!r});
                """
            )
            selenium.run_js(
                """
                let test_pkg = pyodide.pyimport("test_pkg");
                let some_module = pyodide.pyimport("test_pkg.some_module");
                try {
                    assert(() => test_pkg.test1(5) === 26);
                    assert(() => some_module.test1(5) === 26);
                    assert(() => some_module.test2(5) === 24);
                } finally {
                    test_pkg.destroy();
                    some_module.destroy();
                    pyodide.runPython(`
                        import shutil
                        shutil.rmtree("test_pkg")
                    `)
                }
                """
            )
    finally:
        (build_dir / "test_pkg.tar").unlink(missing_ok=True)
        (test_dir / "test_pkg.tar").unlink(missing_ok=True)
