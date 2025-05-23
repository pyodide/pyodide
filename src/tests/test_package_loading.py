import json
import re
import shutil
from pathlib import Path

import pytest
from pytest_pyodide import run_in_pyodide
from pytest_pyodide.fixture import selenium_common
from pytest_pyodide.server import spawn_web_server
from pytest_pyodide.utils import parse_driver_timeout, set_webdriver_script_timeout

from conftest import DIST_PATH, PYODIDE_ROOT


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
        assert "Loading pyparsing" in selenium.logs
        assert "Loaded pyparsing" in selenium.logs

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
    test_html = (PYODIDE_ROOT / "src/templates/test.html").read_text()
    test_html = test_html.replace("./pyodide.js", f"http://{url}:{port}/pyodide.js")
    (tmp_path / "test_temp.html").write_text(test_html)
    pytz_wheel = get_pytz_wheel_name()
    shutil.copy(DIST_PATH / pytz_wheel, tmp_path / pytz_wheel)

    with (
        spawn_web_server(tmp_path) as web_server,
        selenium_common(
            request,
            runtime,
            web_server,
            load_pyodide=False,
            browsers=playwright_browsers,
            script_type="classic",
        ) as selenium,
        set_webdriver_script_timeout(
            selenium, script_timeout=parse_driver_timeout(request.node)
        ),
    ):
        if selenium.browser != "node":
            selenium.goto(f"http://{url}:{web_server[1]}/test_temp.html")
        selenium.load_pyodide()
        selenium.initialize_pyodide()
        selenium.save_state()
        selenium.restore_state()
        if selenium.browser == "node":
            selenium.run_js(f"process.chdir('{tmp_path.resolve()}')")
        selenium.load_package(pytz_wheel)
        selenium.run(
            "import pytz; from pyodide_js import loadedPackages; print(loadedPackages.pytz)"
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


def test_load_package_return(selenium_standalone):
    selenium = selenium_standalone
    package = selenium.run_js("return await pyodide.loadPackage('pyparsing')")

    assert package[0]["name"] == "pyparsing"
    assert package[0]["packageType"] == "package"


@pytest.mark.xfail_browsers(node="Loading urls in node seems to time out right now")
@pytest.mark.parametrize("active_server", ["main", "secondary"])
def test_load_package_return_from_url(
    selenium_standalone, web_server_secondary, active_server
):
    selenium = selenium_standalone
    if active_server == "secondary":
        url, port, _ = web_server_secondary
    elif active_server == "main":
        url = selenium.server_hostname
        port = selenium.server_port
    else:
        raise AssertionError()

    pyparsing_wheel_name = get_pyparsing_wheel_name()
    package = selenium.run_js(
        f"return await pyodide.loadPackage('http://{url}:{port}/{pyparsing_wheel_name}')"
    )

    assert package[0]["name"] == "pyparsing"
    assert package[0]["packageType"] == "package"
    assert package[0]["fileName"] == pyparsing_wheel_name


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
    loaded_packages = [
        x[0]["name"] for x in selenium.run_js(f"return await Promise.all([{promises}])")
    ]
    selenium.run(f"import {packages[0]}")
    selenium.run(f"import {packages[1]}")
    # The log must show that each package is loaded exactly once,
    # including when one package is a dependency of the other
    # ('pyparsing' and 'matplotlib')
    assert selenium.logs.count(f"Loaded {packages[0]}") == 1
    assert selenium.logs.count(f"Loaded {packages[1]}") == 1

    assert loaded_packages == [packages[0], packages[1]] or loaded_packages == [
        packages[1],
        packages[0],
    ]


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


@pytest.mark.requires_dynamic_linking
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
        return pyodide._api.lockfile_packages['regex'].unvendored_tests;
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


@pytest.mark.requires_dynamic_linking
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


def test_find_wheel_metadata_dir():
    from tempfile import NamedTemporaryFile
    from zipfile import ZipFile

    from pyodide._package_loader import find_wheel_metadata_dir

    with NamedTemporaryFile(suffix=".whl") as t:
        z = ZipFile(t, mode="w")
        z.writestr("a.dist-info/METADATA", "")
        z.writestr("b.some-info/METADATA", "")

        z.close()
        t.flush()

        assert find_wheel_metadata_dir(z, ".dist-info") == "a.dist-info"
        assert find_wheel_metadata_dir(z, ".some-info") == "b.some-info"
        assert find_wheel_metadata_dir(z, ".not-exist") is None


def test_wheel_dist_info_dir():
    from tempfile import NamedTemporaryFile
    from zipfile import ZipFile

    from pyodide._package_loader import UnsupportedWheel, wheel_dist_info_dir

    with NamedTemporaryFile(suffix=".whl") as t:
        z = ZipFile(t, mode="w")
        z.writestr("b.some-info/METADATA", "")

        z.close()
        t.flush()

        with pytest.raises(
            UnsupportedWheel, match=".dist-info directory not found in wheel"
        ):
            wheel_dist_info_dir(z, "pkg-name")

    with NamedTemporaryFile(suffix=".whl") as t:
        z = ZipFile(t, mode="w")
        z.writestr("pkg_name.dist-info/METADATA", "")
        z.writestr("b.some-info/METADATA", "")

        z.close()
        t.flush()

        assert wheel_dist_info_dir(z, "pkg_name") == "pkg_name.dist-info"
        assert wheel_dist_info_dir(z, "pkg-name") == "pkg_name.dist-info"

        with pytest.raises(UnsupportedWheel, match="does not start with 'not-package'"):
            wheel_dist_info_dir(z, "not-package")


def test_wheel_data_file_dir():
    from tempfile import NamedTemporaryFile
    from zipfile import ZipFile

    from pyodide._package_loader import wheel_data_file_dir

    with NamedTemporaryFile(suffix=".whl") as t:
        z = ZipFile(t, mode="w")
        z.writestr("anythingelse", "")

        z.close()
        t.flush()

        assert wheel_data_file_dir(z, "pkg_name") is None

    with NamedTemporaryFile(suffix=".whl") as t:
        z = ZipFile(t, mode="w")
        z.writestr("pkg_name.data/etc/hostname", "")
        z.writestr("pkg_name.data/etc/hosts", "")

        z.close()
        t.flush()

        assert wheel_data_file_dir(z, "pkg_name") == "pkg_name.data"
        assert wheel_data_file_dir(z, "pkg-name") == "pkg_name.data"

        assert wheel_data_file_dir(z, "not-package") is None


class DummyDistribution:
    def __init__(
        self,
        name: str,
        source: str | None = None,
        direct_url: dict[str, str] | None = None,
        installer: str | None = None,
        version: str = "0.0.1",
    ):
        self.name = name
        self.version = version
        direct_url_json = json.dumps(direct_url) if direct_url else None
        self._files: dict[str, str | None] = {
            "PYODIDE_SOURCE": source,
            "direct_url.json": direct_url_json,
            "INSTALLER": installer,
        }

    @property
    def dist_info_name(self):
        # https://packaging.python.org/en/latest/specifications/name-normalization/#normalization
        normalized_name = re.sub(r"[-_.]+", "-", self.name).lower()
        return f"{normalized_name}-{self.version}.dist-info"

    def write(self, base_dir: Path) -> None:
        dist_info_dir = base_dir / self.dist_info_name
        dist_info_dir.mkdir(exist_ok=True)
        for key, value in self._files.items():
            if value is not None:
                (dist_info_dir / key).write_text(value)
        with (dist_info_dir / "METADATA").open("w") as f:
            # fmt: off
            f.write(
                "Metadata-Version: 2.1\n"
                f"Name: {self.name}\n"
                f"Version: {self.version}\n"
            )
            # fmt: on

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
    ("Unknown", DummyDistribution("H-H")),
]


@pytest.mark.parametrize("result,dist", result_dist_pairs)
def test_get_dist_source(result, dist, tmp_path):
    from pyodide._package_loader import get_dist_source

    dist.write(tmp_path)

    assert (dist.name, result) == get_dist_source(tmp_path / dist.dist_info_name)


def test_init_loaded_packages(monkeypatch, tmp_path):
    from pyodide import _package_loader

    class loadedPackagesCls:
        pass

    loadedPackages = loadedPackagesCls()
    monkeypatch.setattr(_package_loader, "SITE_PACKAGES", tmp_path)
    monkeypatch.setattr(_package_loader, "loadedPackages", loadedPackages)
    dists = [dist for [_, dist] in result_dist_pairs]
    for dist in dists:
        dist.write(tmp_path)
    _package_loader.init_loaded_packages()

    for [result, dist] in result_dist_pairs:
        assert hasattr(loadedPackages, dist.name)
        assert getattr(loadedPackages, dist.name) == result


@pytest.mark.xfail_browsers(node="Some fetch trouble")
@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
@pytest.mark.requires_dynamic_linking
def test_custom_lockfile(selenium_standalone_noload):
    selenium = selenium_standalone_noload
    lock = selenium.run_js(
        """
        let pyodide = await loadPyodide({fullStdLib: false, packages: ["micropip"]});
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
                let pyodide = await loadPyodide({fullStdLib: false, lockFileURL: "custom_lockfile.json", packages: ["hypothesis"] });
                return pyodide.runPython("import hypothesis; hypothesis.__version__")
                """
            )
            == "6.47.3"
        )
    finally:
        custom_lockfile.unlink()


def test_custom_lockfile_different_dir(selenium_standalone_noload, tmp_path):
    selenium = selenium_standalone_noload

    orig_lockfile = DIST_PATH / "pyodide-lock.json"
    custom_lockfile_name = "custom-lockfile.json"

    test_file_name = "dummy_pkg-0.1.0-py3-none-any.whl"
    test_file_path = Path(__file__).parent / "wheels" / test_file_name

    lockfile_content = json.loads(orig_lockfile.read_text())
    lockfile_content["packages"] = {
        "dummy-pkg": {
            "name": "dummy_pkg",
            "version": "0.1.0",
            "unvendor_tests": False,
            "sha256": "22fc6330153be71220aea157ab135c53c7d34ff1a6d1d1a4705c95eef1a6f262",
            "depends": [],
            "file_name": test_file_name,
            "install_dir": "site",
            "package_type": "package",
            "imports": [],
        }
    }

    custom_lockfile_path = tmp_path / "custom-lockfile.json"
    custom_lockfile_path.write_text(json.dumps(lockfile_content))
    shutil.copy(test_file_path, tmp_path / test_file_name)

    with spawn_web_server(tmp_path) as web_server:
        url, port, _ = web_server
        lockfile_url = f"http://{url}:{port}/{custom_lockfile_name}"
        selenium.run_js(
            f"""
            let pyodide = await loadPyodide({{fullStdLib: false, lockFileURL: {lockfile_url!r} }});
            await pyodide.loadPackage("dummy_pkg", {{ checkIntegrity: false }});
            return pyodide.runPython("import dummy_pkg;")
            """
        )


@pytest.mark.parametrize(
    "load_name, normalized_name, real_name",
    [
        # TODO: find a better way to test this without relying on the core packages set
        ("fpcast-test", "fpcast-test", "fpcast-test"),
        ("fpcast_test", "fpcast-test", "fpcast-test"),
        ("Jinja2", "jinja2", "Jinja2"),
        ("jinja2", "jinja2", "Jinja2"),
        ("pydoc_data", "pydoc-data", "pydoc_data"),
        ("pydoc-data", "pydoc-data", "pydoc_data"),
    ],
)
@pytest.mark.requires_dynamic_linking  # only required for fpcast-test
def test_normalized_name(selenium_standalone, load_name, normalized_name, real_name):
    selenium = selenium_standalone

    selenium.run_js(
        f"""
        const msgs = [];
        await pyodide.loadPackage(
            "{load_name}",
            {{
                messageCallback: (msg) => msgs.push(msg),
            }}
        )

        const loaded = Object.keys(pyodide.loadedPackages);
        assert(() => loaded.includes("{real_name}"));

        const loadStartMsgs = msgs.filter((msg) => msg.startsWith("Loading"));
        const loadEndMsgs = msgs.filter((msg) => msg.startsWith("Loaded"));

        assert(() => loadStartMsgs.some((msg) => msg.includes("{real_name}")));
        assert(() => loadEndMsgs.some((msg) => msg.includes("{real_name}")));
        """
    )


def test_data_files_support(selenium_standalone, httpserver):
    selenium = selenium_standalone

    test_file_name = "dummy_pkg-0.1.0-py3-none-any.whl"
    test_file_path = Path(__file__).parent / "wheels" / test_file_name
    test_file_data = test_file_path.read_bytes()

    httpserver.expect_oneshot_request("/" + test_file_name).respond_with_data(
        test_file_data,
        content_type="application/zip",
        headers={"Access-Control-Allow-Origin": "*"},
        status=200,
    )
    request_url = httpserver.url_for("/" + test_file_name)

    selenium.run_js(
        f"""
        await pyodide.loadPackage("{request_url}");
        """
    )

    @run_in_pyodide
    def _run(selenium):
        import sys
        from pathlib import Path

        import dummy_pkg

        assert dummy_pkg

        assert (Path(sys.prefix) / "share" / "datafile").is_file(), "datafile not found"
        assert (Path(sys.prefix) / "etc" / "datafile2").is_file(), "datafile2 not found"

    _run(selenium)


def test_install_api(selenium_standalone, httpserver):
    selenium = selenium_standalone

    test_file_name = "dummy_pkg-0.1.0-py3-none-any.whl"
    test_file_path = Path(__file__).parent / "wheels" / test_file_name
    test_file_data = test_file_path.read_bytes()
    install_dir = "/random_install_dir"

    httpserver.expect_oneshot_request("/" + test_file_name).respond_with_data(
        test_file_data,
        content_type="application/zip",
        headers={"Access-Control-Allow-Origin": "*"},
        status=200,
    )
    request_url = httpserver.url_for("/" + test_file_name)

    selenium.run_js(
        f"""
        wheelData = await fetch("{request_url}");
        wheelDataArr = new Uint8Array(await wheelData.arrayBuffer());
        await pyodide._api.install(
          wheelDataArr,
          "{test_file_name}",
          "{install_dir}",
          new Map([["INSTALLER", "pytest"]])
        );
        """
    )

    @run_in_pyodide
    def _run(selenium, pkg_dir):
        import pathlib

        d = pathlib.Path(pkg_dir)
        assert d.is_dir(), f"Directory {d} not found"
        assert (d / "dummy_pkg-0.1.0.dist-info").is_dir(), (
            "dist-info directory not found"
        )
        assert (d / "dummy_pkg-0.1.0.dist-info" / "INSTALLER").is_file(), (
            "INSTALLER file not found"
        )
        assert (d / "dummy_pkg").is_dir(), "package directory not found"

    _run(selenium, install_dir)
