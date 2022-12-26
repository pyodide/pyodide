import json
import shutil
from pathlib import Path

import pytest
from pytest_pyodide.fixture import selenium_common
from pytest_pyodide.server import spawn_web_server
from pytest_pyodide.utils import parse_driver_timeout, set_webdriver_script_timeout

from conftest import DIST_PATH, ROOT_PATH


def get_pyparsing_wheel_name() -> str:
    return list(DIST_PATH.glob("pyparsing*.whl"))[0].name


def get_pytz_wheel_name() -> str:
    return list(DIST_PATH.glob("pytz*.whl"))[0].name


@pytest.mark.xfail_browsers(node="Loading urls in node seems to time out right now")
@pytest.mark.parametrize("active_server", ["main", "secondary"])
def test_load_from_url(selenium_standalone, web_server_secondary, active_server):
    selenium = selenium_standalone
    if active_server == "secondary":
        url, port, log_main = web_server_secondary
        log_backup = selenium.server_log
    elif active_server == "main":
        _, _, log_backup = web_server_secondary
        log_main = selenium.server_log
        url = selenium.server_hostname
        port = selenium.server_port
    else:
        raise AssertionError()

    with log_backup.open("r") as fh_backup, log_main.open("r") as fh_main:

        # skip existing log lines
        fh_main.seek(0, 2)
        fh_backup.seek(0, 2)

        pyparsing_wheel_name = get_pyparsing_wheel_name()
        selenium.load_package(f"http://{url}:{port}/{pyparsing_wheel_name}")
        assert "Skipping unknown package" not in selenium.logs

        # check that all resources were loaded from the active server
        txt = fh_main.read()
        assert f'"GET /{pyparsing_wheel_name} HTTP/1.1" 200' in txt

        # no additional resources were loaded from the other server
        assert len(fh_backup.read()) == 0

    selenium.run(
        """
        from pyparsing import Word, alphas
        repr(Word(alphas).parseString('hello'))
        """
    )

    pytz_wheel_name = get_pytz_wheel_name()
    selenium.load_package(f"http://{url}:{port}/{pytz_wheel_name}")
    selenium.run("import pytz")


def test_load_relative_url(
    request, runtime, web_server_main, playwright_browsers, tmp_path
):
    url, port, _ = web_server_main
    test_html = (ROOT_PATH / "src/templates/test.html").read_text()
    test_html = test_html.replace("./pyodide.js", f"http://{url}:{port}/pyodide.js")
    (tmp_path / "test.html").write_text(test_html)
    pytz_wheel = get_pytz_wheel_name()
    pytz1_wheel = pytz_wheel.replace("pytz", "pytz1")
    shutil.copy(DIST_PATH / pytz_wheel, tmp_path / pytz1_wheel)

    with spawn_web_server(tmp_path) as web_server, selenium_common(
        request,
        runtime,
        web_server,
        load_pyodide=True,
        browsers=playwright_browsers,
        script_type="classic",
    ) as selenium, set_webdriver_script_timeout(
        selenium, script_timeout=parse_driver_timeout(request.node)
    ):
        if selenium.browser == "node":
            selenium.run_js(f"process.chdir('{tmp_path.resolve()}')")
        selenium.load_package(pytz1_wheel)
        selenium.run(
            "import pytz; from pyodide_js import loadedPackages; print(loadedPackages.pytz1)"
        )


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
    selenium_standalone.load_package("http://some_url/pyparsing-3.0.6-py3-none-any.whl")
    assert (
        "URI mismatch, attempting to load package pyparsing" in selenium_standalone.logs
    )


def test_invalid_package_name(selenium):
    with pytest.raises(
        selenium.JavascriptException,
        match=r"No known package with name 'wrong name\+\$'",
    ):
        selenium.load_package("wrong name+$")
    with pytest.raises(
        selenium.JavascriptException,
        match="No known package with name 'tcp://some_url'",
    ):
        selenium.load_package("tcp://some_url")


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
    assert (
        selenium.logs.count(f"Loaded {packages[0]}, {packages[1]}") == 1
        or selenium.logs.count(f"Loaded {packages[1]}, {packages[0]}") == 1
    )


@pytest.mark.parametrize(
    "packages", [["pyparsing", "pytz"], ["pyparsing", "packaging"]], ids="-".join
)
def test_load_packages_sequential(selenium_standalone, packages):
    selenium = selenium_standalone
    promises = ",".join(f'pyodide.loadPackage("{x}")' for x in packages)
    selenium.run_js(f"return Promise.all([{promises}])")
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
    with pytest.raises(
        selenium.JavascriptException, match="No known package with name 'pytz2'"
    ):
        selenium.load_package("pytz2")
    selenium.load_package("pyparsing")
    assert "Loaded pytz" in selenium.logs
    assert "Loaded pyparsing" in selenium.logs


@pytest.mark.skip_refcount_check
def test_load_failure_retry(selenium_standalone):
    """Check that a package can be loaded after failing to load previously"""
    selenium = selenium_standalone
    selenium.load_package("http://invalidurl/pytz-2021.3-py3-none-any.whl")
    assert selenium.logs.count("Loading pytz") == 1
    assert selenium.logs.count("The following error occurred while loading pytz:") == 1
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == []
    selenium.load_package("pytz")
    selenium.run("import pytz")
    assert selenium.run_js("return Object.keys(pyodide.loadedPackages)") == ["pytz"]


def test_load_package_unknown(selenium_standalone):
    pyparsing_wheel_name = get_pyparsing_wheel_name()
    shutil.copyfile(
        DIST_PATH / pyparsing_wheel_name,
        DIST_PATH / "pyparsing-custom-3.0.6-py3-none-any.whl",
    )

    try:
        selenium_standalone.load_package("./pyparsing-custom-3.0.6-py3-none-any.whl")
    finally:
        (DIST_PATH / "pyparsing-custom-3.0.6-py3-none-any.whl").unlink()

    assert selenium_standalone.run_js(
        "return pyodide.loadedPackages.hasOwnProperty('pyparsing-custom')"
    )


def test_load_twice(selenium_standalone):
    selenium_standalone.load_package("pytz")
    selenium_standalone.load_package("pytz")
    assert "No new packages to load" in selenium_standalone.logs


def test_load_twice_different_source(selenium_standalone):
    selenium_standalone.load_package(
        [
            "https://foo/pytz-2021.3-py3-none-any.whl",
            "https://bar/pytz-2021.3-py3-none-any.whl",
        ]
    )
    assert (
        "Loading same package pytz from https://bar/pytz-2021.3-py3-none-any.whl and https://foo/pytz-2021.3-py3-none-any.whl"
        in selenium_standalone.logs
    )


def test_load_twice_same_source(selenium_standalone):
    selenium_standalone.load_package(
        [
            "https://foo/pytz-2021.3-py3-none-any.whl",
            "https://foo/pytz-2021.3-py3-none-any.whl",
        ]
    )
    assert "Loading same package pytz" not in selenium_standalone.logs


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
        return pyodide._api.repodata_packages['regex'].unvendored_tests;
        """
    )


def test_install_archive(selenium):
    test_dir = Path(__file__).parent
    # TODO: first argument actually works as a path due to implementation,
    # maybe it can be proposed to typeshed?
    shutil.make_archive(
        str(test_dir / "test_pkg"), "gztar", root_dir=test_dir, base_dir="test_pkg"
    )
    build_test_pkg = DIST_PATH / "test_pkg.tar.gz"
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
        (DIST_PATH / "test_pkg.tar.gz").unlink(missing_ok=True)
        (test_dir / "test_pkg.tar.gz").unlink(missing_ok=True)


def test_load_bad_so_file(selenium):
    # If we load a bad so file, we should catch the error, ignore it (and log a
    # warning)
    selenium.run_js(
        """
        pyodide.FS.writeFile("/a.so", new Uint8Array(4))
        await pyodide._api.loadDynlib("/a.so");
        """
    )
    assert (
        "Failed to load dynlib /a.so. We probably just tried to load a linux .so file or something."
        in selenium.logs
    )


def test_should_load_dynlib():
    import sysconfig

    from pyodide._package_loader import should_load_dynlib

    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX")
    assert ext_suffix
    should_load = [
        "a.so",
        "a.so.1.2.3",
        "a/b.so",
        "b/b.so",
        "a/b/c/d.so",
        "a/b/c/d.abi3.so",
        "x.abi3.so",
        "a.b.c.so",
        "a-weird-name.stuff-with-dashes.so",
        f"x.{ext_suffix}",
    ]
    should_not_load = [
        "a",
        "a.py",
        "a.txt",
        "a/b.txt",
        "a/b.py",
        "b/a.py",
        "q.cpython-38-x86_64-linux-gnu.so",
        "q.cpython-38-x86_64-linux-gnu.so",
        "q" + ext_suffix.replace("cpython", "pypy"),
        "q.cpython-32mu.so",
        "x.so.a.b.c",
    ]
    for file in should_load:
        assert should_load_dynlib(file)
    for file in should_not_load:
        assert not should_load_dynlib(file)


def test_get_dynlibs():
    import tarfile
    from tempfile import NamedTemporaryFile
    from zipfile import ZipFile

    from pyodide._package_loader import get_dynlibs

    files = [
        "a",
        "a.so",
        "a.py",
        "a.txt",
        "a/b.so",
        "a/b.txt",
        "a/b.py",
        "b/a.py",
        "b/b.so",
        "a/b/c/d.so",
    ]
    so_files = sorted("/p/" + f for f in files if f.endswith(".so"))
    with NamedTemporaryFile(suffix=".bz") as t:
        x = tarfile.open(mode="x:bz2", fileobj=t)
        for file in files:
            x.addfile(tarfile.TarInfo(file))
        x.close()
        t.flush()
        assert sorted(get_dynlibs(t, ".bz", Path("/p"))) == so_files
    with NamedTemporaryFile(suffix=".zip") as t:
        x2 = ZipFile(t, mode="w")
        for file in files:
            x2.writestr(file, "")
        x2.close()
        t.flush()
        assert sorted(get_dynlibs(t, ".zip", Path("/p"))) == so_files


class DummyDistribution:
    def __init__(
        self,
        name: str,
        source: str | None = None,
        direct_url: dict[str, str] | None = None,
        installer: str | None = None,
    ):
        self.name = name
        direct_url_json = json.dumps(direct_url) if direct_url else None
        self._files: dict[str, str | None] = {
            "PYODIDE_SOURCE": source,
            "direct_url.json": direct_url_json,
            "INSTALLER": installer,
        }

    def read_text(self, key: str) -> str | None:
        return self._files.get(key)

    def __repr__(self):
        return self.name


result_dist_pairs = [
    ("default channel", DummyDistribution("A", source="pyodide")),
    (
        "default channel",
        DummyDistribution(
            "B",
            source="pyodide",
            direct_url={"url": "http://some.pkg.src/a/b/c.whl"},
            installer="pip",
        ),
    ),
    (
        "http://some.pkg.src/a/b/c.whl",
        DummyDistribution("C", source="http://some.pkg.src/a/b/c.whl"),
    ),
    (
        "http://some.pkg.src/a/b/c.whl",
        DummyDistribution(
            "D",
            source="http://some.pkg.src/a/b/c.whl",
            direct_url={"url": "http://a.b.c/x/y/z.whl"},
            installer="pip",
        ),
    ),
    (
        "http://a.b.c/x/y/z.whl",
        DummyDistribution(
            "E", direct_url={"url": "http://a.b.c/x/y/z.whl"}, installer="pip"
        ),
    ),
    ("pip (index unknown)", DummyDistribution("F", installer="pip")),
    ("other (index unknown)", DummyDistribution("G", installer="other")),
    ("Unknown", DummyDistribution("H")),
]


@pytest.mark.parametrize("result,dist", result_dist_pairs)
def test_get_dist_source(result, dist):
    from pyodide._package_loader import get_dist_source

    assert result == get_dist_source(dist)


def test_init_loaded_packages(monkeypatch):
    from pyodide import _package_loader

    class loadedPackagesCls:
        pass

    loadedPackages = loadedPackagesCls()
    monkeypatch.setattr(_package_loader, "loadedPackages", loadedPackages)
    dists = [dist for [_, dist] in result_dist_pairs]
    monkeypatch.setattr(_package_loader, "importlib_distributions", lambda: dists)
    _package_loader.init_loaded_packages()

    for [result, dist] in result_dist_pairs:
        assert hasattr(loadedPackages, dist.name)
        assert getattr(loadedPackages, dist.name) == result


@pytest.mark.xfail_browsers(node="Some fetch trouble")
@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_custom_lockfile(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    lock = selenium.run_js(
        """
        let pyodide = await loadPyodide({fullStdLib: false});
        await pyodide.loadPackage("micropip")
        return pyodide.runPythonAsync(`
            import micropip
            await micropip.install("hypothesis==6.47.3")
            micropip.freeze()
        `);
        """
    )
    custom_lockfile = DIST_PATH / "custom_lockfile.json"
    custom_lockfile.write_text(lock)

    try:
        assert (
            selenium.run_js(
                """
                let pyodide = await loadPyodide({fullStdLib: false, lockFileURL: "custom_lockfile.json" });
                await pyodide.loadPackage("hypothesis");
                return pyodide.runPython("import hypothesis; hypothesis.__version__")
                """
            )
            == "6.47.3"
        )
    finally:
        custom_lockfile.unlink()
