import io
import sys
import zipfile
from pathlib import Path

import pytest
from pyodide_test_runner import run_in_pyodide, spawn_web_server

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from importlib.metadata import PackageNotFoundError, distributions

try:
    import micropip
except ImportError:
    pass


def _mock_importlib_version(name: str) -> str:
    dists = _mock_importlib_distributions()
    for dist in dists:
        if dist.name == name:
            return dist.version
    raise PackageNotFoundError(name)


def _mock_importlib_distributions():
    from micropip._micropip import WHEEL_BASE

    return distributions(path=[WHEEL_BASE])


@pytest.fixture
def mock_importlib(monkeypatch):
    from micropip import _micropip

    monkeypatch.setattr(_micropip, "importlib_version", _mock_importlib_version)
    monkeypatch.setattr(
        _micropip, "importlib_distributions", _mock_importlib_distributions
    )


DUMMY_IDX = 0


@pytest.fixture
def dummy_pkg_name():
    global DUMMY_IDX
    DUMMY_IDX += 1
    return f"dummy{DUMMY_IDX}"


class Wildcard:
    def __eq__(self, other):
        return True


def make_wheel_filename(name: str, version: str, platform: str = "generic"):
    if platform == "generic":
        platform_str = "py3-none-any"
    elif platform == "emscripten":
        platform_str = "cp310-cp310-emscripten_wasm32"
    elif platform == "native":
        platform_str = "cp310-cp310-manylinux_2_31_x86_64"
    else:
        platform_str = platform

    return f"{name.replace('-', '_').lower()}-{version}-{platform_str}.whl"


class mock_fetch_cls:
    def __init__(self):
        self.releases_map = {}
        self.metadata_map = {}
        self.top_level_map = {}

    def add_pkg_version(
        self,
        name: str,
        version: str = "1.0.0",
        *,
        requirements: list[str] | None = None,
        extras: dict[str, list[str]] | None = None,
        platform: str = "generic",
        top_level: list[str] | None = None,
    ):
        if requirements is None:
            requirements = []
        if extras is None:
            extras = {}
        if top_level is None:
            top_level = []
        if name not in self.releases_map:
            self.releases_map[name] = {"releases": {}}
        releases = self.releases_map[name]["releases"]
        filename = make_wheel_filename(name, version, platform)
        releases[version] = [
            {
                "filename": filename,
                "url": filename,
                "digests": {
                    "sha256": Wildcard(),
                },
            }
        ]
        metadata = [("Name", name), ("Version", version)] + [
            ("Requires-Dist", req) for req in requirements
        ]
        for extra, reqs in extras.items():
            metadata += [("Provides-Extra", extra)] + [
                ("Requires-Dist", f"{req}; extra == {extra!r}") for req in reqs
            ]
        self.metadata_map[filename] = metadata
        self.top_level_map[filename] = top_level

    async def _get_pypi_json(self, pkgname, kwargs):
        try:
            print("_get_pypi_json", pkgname, self.releases_map[pkgname])
            return self.releases_map[pkgname]
        except KeyError as e:
            raise ValueError(
                f"Can't fetch metadata for '{pkgname}' from PyPI. "
                "Please make sure you have entered a correct package name."
            ) from e

    async def _fetch_bytes(self, url, kwargs):
        from micropip._micropip import WheelInfo

        wheel_info = WheelInfo.from_url(url)
        version = wheel_info.version
        name = wheel_info.name
        filename = wheel_info.filename
        metadata = self.metadata_map[filename]
        metadata_str = "\n".join(": ".join(x) for x in metadata)
        toplevel = self.top_level_map[filename]
        toplevel_str = "\n".join(toplevel)

        metadata_dir = f"{name}-{version}.dist-info"

        with io.BytesIO() as tmp:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as archive:

                def write_file(filename, contents):
                    archive.writestr(f"{metadata_dir}/{filename}", contents)

                write_file("METADATA", metadata_str)
                write_file("WHEEL", "Wheel-Version: 1.0")
                write_file("top_level.txt", toplevel_str)

            tmp.seek(0)

            return tmp.read()


@pytest.fixture
def mock_fetch(monkeypatch):
    pytest.importorskip("packaging")
    from micropip import _micropip

    result = mock_fetch_cls()
    monkeypatch.setattr(_micropip, "_get_pypi_json", result._get_pypi_json)
    monkeypatch.setattr(_micropip, "fetch_bytes", result._fetch_bytes)
    return result


@pytest.fixture
def selenium_standalone_micropip(selenium_standalone):
    """Import micropip before entering test so that global initialization of
    micropip doesn't count towards hiwire refcount.
    """
    selenium_standalone.run_js(
        """
        await pyodide.loadPackage("micropip");
        pyodide.runPython("import micropip");
        """
    )
    yield selenium_standalone


def test_install_simple(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    assert (
        selenium.run_js(
            """
            return await pyodide.runPythonAsync(`
                import os
                import micropip
                from pyodide import to_js
                # Package 'pyodide-micropip-test' has dependency on 'snowballstemmer'
                # It is used to test markers support
                await micropip.install('pyodide-micropip-test')
                import snowballstemmer
                stemmer = snowballstemmer.stemmer('english')
                to_js(stemmer.stemWords('go going goes gone'.split()))
            `);
            """
        )
        == ["go", "go", "goe", "gone"]
    )


def test_parse_wheel_url():
    pytest.importorskip("packaging")
    from micropip._micropip import WheelInfo

    url = "https://a/snowballstemmer-2.0.0-py2.py3-none-any.whl"
    wheel = WheelInfo.from_url(url)
    assert wheel.name == "snowballstemmer"
    assert str(wheel.version) == "2.0.0"
    assert wheel.digests is None
    assert wheel.filename == "snowballstemmer-2.0.0-py2.py3-none-any.whl"
    assert wheel.packagetype == "bdist_wheel"
    assert wheel.python_version == "py2.py3"
    assert wheel.abi_tag == "none"
    assert wheel.platform == "any"
    assert wheel.url == url

    msg = "not a valid wheel file name"
    with pytest.raises(ValueError, match=msg):
        url = "https://a/snowballstemmer-2.0.0-py2.whl"
        wheel = WheelInfo.from_url(url)

    url = "http://scikit_learn-0.22.2.post1-cp35-cp35m-macosx_10_9_intel.whl"
    wheel = WheelInfo.from_url(url)
    assert wheel.name == "scikit_learn"
    assert wheel.platform == "macosx_10_9_intel"


@pytest.mark.parametrize("base_url", ["'{base_url}'", "'.'"])
def test_install_custom_url(selenium_standalone_micropip, base_url):
    selenium = selenium_standalone_micropip

    with spawn_web_server(Path(__file__).parent / "test") as server:
        server_hostname, server_port, _ = server
        base_url = f"http://{server_hostname}:{server_port}/"
        url = base_url + "snowballstemmer-2.0.0-py2.py3-none-any.whl"

        selenium.run_js(
            f"""
            let url = '{url}';
            let resp = await fetch(url);
            await pyodide.runPythonAsync(`
                import micropip
                await micropip.install('${{url}}')
                import snowballstemmer
            `);
            """
        )


def create_transaction(Transaction):
    return Transaction(
        wheels=[],
        locked={},
        keep_going=True,
        deps=True,
        pre=False,
        pyodide_packages=[],
        failed=[],
        ctx={"extra": ""},
        fetch_kwargs={},
    )


@pytest.mark.asyncio
async def test_add_requirement():
    pytest.importorskip("packaging")
    from micropip._micropip import Transaction

    with spawn_web_server(Path(__file__).parent / "test") as server:
        server_hostname, server_port, _ = server
        base_url = f"http://{server_hostname}:{server_port}/"
        url = base_url + "snowballstemmer-2.0.0-py2.py3-none-any.whl"

        transaction = create_transaction(Transaction)
        await transaction.add_requirement(url)

    wheel = transaction.wheels[0]
    assert wheel.name == "snowballstemmer"
    assert str(wheel.version) == "2.0.0"
    assert wheel.filename == "snowballstemmer-2.0.0-py2.py3-none-any.whl"
    assert wheel.packagetype == "bdist_wheel"
    assert wheel.python_version == "py2.py3"
    assert wheel.abi_tag == "none"
    assert wheel.platform == "any"
    assert wheel.url == url


@pytest.mark.asyncio
async def test_add_requirement_marker(mock_importlib):
    pytest.importorskip("packaging")
    from micropip._micropip import Transaction

    transaction = create_transaction(Transaction)

    await transaction.gather_requirements(
        [
            "werkzeug",
            'contextvars ; python_version < "3.7"',
            'aiocontextvars ; python_version < "3.7"',
            "numpy ; extra == 'full'",
            "zarr ; extra == 'full'",
            "numpy ; extra == 'jupyter'",
            "ipykernel ; extra == 'jupyter'",
            "numpy ; extra == 'socketio'",
            "python-socketio[client] ; extra == 'socketio'",
        ],
    )
    assert len(transaction.wheels) == 1


def test_last_version_from_pypi():
    pytest.importorskip("packaging")
    from packaging.requirements import Requirement

    from micropip._micropip import find_wheel

    requirement = Requirement("dummy_module")
    versions = ["0.0.1", "0.15.5", "0.9.1"]

    # building metadata as returned from
    # https://pypi.org/pypi/{pkgname}/json
    releases = {}
    for v in versions:
        filename = f"dummy_module-{v}-py3-none-any.whl"
        releases[v] = [{"filename": filename, "url": filename, "digests": None}]

    metadata = {"releases": releases}

    # get version number from find_wheel
    wheel = find_wheel(metadata, requirement)

    assert str(wheel.version) == "0.15.5"


@pytest.mark.asyncio
async def test_install_non_pure_python_wheel():
    pytest.importorskip("packaging")
    from micropip._micropip import Transaction

    msg = "not a pure Python 3 wheel"
    with pytest.raises(ValueError, match=msg):
        url = "http://scikit_learn-0.22.2.post1-cp35-cp35m-macosx_10_9_intel.whl"
        transaction = create_transaction(Transaction)
        await transaction.add_requirement(url)


def test_install_different_version(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install(
                "https://files.pythonhosted.org/packages/89/06/2c2d3034b4d6bf22f2a4ae546d16925898658a33b4400cfb7e2c1e2871a3/pytz-2020.5-py2.py3-none-any.whl"
            );
        `);
        """
    )
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import pytz
            assert pytz.__version__ == "2020.5"
        `);
        """
    )


def test_install_different_version2(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install(
                "pytz == 2020.5"
            );
        `);
        """
    )
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import pytz
            assert pytz.__version__ == "2020.5"
        `);
        """
    )


@pytest.mark.parametrize("jinja2", ["jinja2", "Jinja2"])
def test_install_mixed_case2(selenium_standalone_micropip, jinja2):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        f"""
        await pyodide.loadPackage("micropip");
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install("{jinja2}")
            import jinja2
        `);
        """
    )


@pytest.mark.asyncio
async def test_install_keep_going(mock_fetch: mock_fetch_cls, dummy_pkg_name: str):
    dep1 = f"{dummy_pkg_name}-dep1"
    dep2 = f"{dummy_pkg_name}-dep2"
    mock_fetch.add_pkg_version(dummy_pkg_name, requirements=[dep1, dep2])
    mock_fetch.add_pkg_version(dep1, platform="native")
    mock_fetch.add_pkg_version(dep2, platform="native")

    # report order is non-deterministic
    msg = f"({dep1}|{dep2}).*({dep2}|{dep1})"
    with pytest.raises(ValueError, match=msg):
        await micropip.install(dummy_pkg_name, keep_going=True)


@pytest.mark.asyncio
async def test_install_version_compare_prerelease(
    mock_fetch: mock_fetch_cls, dummy_pkg_name: str, mock_importlib: None
):
    version_old = "3.2.0"
    version_new = "3.2.1a1"

    mock_fetch.add_pkg_version(dummy_pkg_name, version_old)
    mock_fetch.add_pkg_version(dummy_pkg_name, version_new)

    await micropip.install(f"{dummy_pkg_name}=={version_new}")
    await micropip.install(f"{dummy_pkg_name}>={version_old}")

    installed_pkgs = micropip.list()
    # Older version should not be installed
    assert installed_pkgs[dummy_pkg_name].version == version_new


@pytest.mark.asyncio
async def test_install_no_deps(
    mock_fetch: mock_fetch_cls, dummy_pkg_name: str, mock_importlib: None
):
    dep_pkg_name = "dependency_dummy"
    mock_fetch.add_pkg_version(dummy_pkg_name, requirements=[dep_pkg_name])
    mock_fetch.add_pkg_version(dep_pkg_name)

    await micropip.install(dummy_pkg_name, deps=False)

    assert dummy_pkg_name in micropip.list()
    assert dep_pkg_name not in micropip.list()


@pytest.mark.asyncio
@pytest.mark.parametrize("pre", [True, False])
async def test_install_pre(
    mock_fetch: mock_fetch_cls, mock_importlib: None, pre: bool, dummy_pkg_name: str
):
    version_alpha = "2.0.1a1"
    version_stable = "1.0.0"

    version_should_select = version_alpha if pre else version_stable

    mock_fetch.add_pkg_version(dummy_pkg_name, version_stable)
    mock_fetch.add_pkg_version(dummy_pkg_name, version_alpha)
    await micropip.install(dummy_pkg_name, pre=pre)
    assert micropip.list()[dummy_pkg_name].version == version_should_select


@pytest.mark.asyncio
async def test_fetch_wheel_fail(monkeypatch):
    pytest.importorskip("packaging")
    from micropip import _micropip

    def _mock_fetch_bytes(arg, *args, **kwargs):
        raise OSError(f"Request for {arg} failed with status 404: Not Found")

    monkeypatch.setattr(_micropip, "fetch_bytes", _mock_fetch_bytes)

    msg = "Access-Control-Allow-Origin"
    with pytest.raises(ValueError, match=msg):
        await _micropip.install("htps://x.com/xxx-1.0.0-py3-none-any.whl")


@pytest.mark.asyncio
async def test_list_pypi_package(
    mock_fetch: mock_fetch_cls, mock_importlib: None, dummy_pkg_name: str
):
    mock_fetch.add_pkg_version(dummy_pkg_name)

    await micropip.install(dummy_pkg_name)
    pkg_list = micropip.list()
    assert dummy_pkg_name in pkg_list
    assert pkg_list[dummy_pkg_name].source.lower() == "pypi"


@pytest.mark.asyncio
async def test_list_wheel_package(
    mock_fetch: mock_fetch_cls, mock_importlib: None, dummy_pkg_name: str
):
    mock_fetch.add_pkg_version(dummy_pkg_name)
    dummy_url = f"https://dummy.com/{dummy_pkg_name}-1.0.0-py3-none-any.whl"

    await micropip.install(dummy_url)

    pkg_list = micropip.list()
    assert dummy_pkg_name in pkg_list
    assert pkg_list[dummy_pkg_name].source.lower() == dummy_url


@pytest.mark.asyncio
async def test_list_wheel_name_mismatch(mock_fetch: mock_fetch_cls, mock_importlib):
    dummy_pkg_name = "dummy-Dummy"
    mock_fetch.add_pkg_version(dummy_pkg_name)
    dummy_url = "https://dummy.com/dummy_dummy-1.0.0-py3-none-any.whl"

    await micropip.install(dummy_url)

    pkg_list = micropip.list()
    assert dummy_pkg_name in pkg_list
    assert pkg_list[dummy_pkg_name].source.lower() == dummy_url


def test_list_pyodide_package(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import micropip
            await micropip.install(
                "regex"
            );
        `);
        """
    )
    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
            import micropip
            pkgs = micropip.list()
            assert "regex" in pkgs
            assert pkgs["regex"].source.lower() == "pyodide"
        `);
        """
    )


def test_list_loaded_from_js(selenium_standalone_micropip):
    selenium = selenium_standalone_micropip
    selenium.run_js(
        """
        await pyodide.loadPackage("regex");
        await pyodide.runPythonAsync(`
            import micropip
            pkgs = micropip.list()
            assert "regex" in pkgs
            assert pkgs["regex"].source.lower() == "pyodide"
        `);
        """
    )


@pytest.mark.skip_refcount_check
@run_in_pyodide(packages=["micropip"])
async def test_install_with_credentials():
    import json
    from unittest.mock import MagicMock, patch

    import micropip

    fetch_response_mock = MagicMock()

    async def myfunc():
        return json.dumps(dict())

    fetch_response_mock.string.side_effect = myfunc

    @patch("micropip._compat_in_pyodide.pyfetch", return_value=fetch_response_mock)
    async def call_micropip_install(pyfetch_mock):
        try:
            await micropip.install("pyodide-micropip-test", credentials="include")
        except BaseException:
            # The above will raise an exception as the mock data is garbage
            # but it is sufficient for this test
            pass
        pyfetch_mock.assert_called_with(
            "https://pypi.org/pypi/pyodide-micropip-test/json", credentials="include"
        )

    await call_micropip_install()


@pytest.mark.asyncio
async def test_freeze(
    mock_fetch: mock_fetch_cls, dummy_pkg_name: str, mock_importlib: None
):
    pkg = dummy_pkg_name
    dep1 = f"{pkg}-dep1"
    dep2 = f"{pkg}-dep2"
    toplevel = [["abc", "def", "geh"], ["c", "h", "i"], ["a12", "b13"]]

    mock_fetch.add_pkg_version(pkg, requirements=[dep1, dep2], top_level=toplevel[0])
    mock_fetch.add_pkg_version(dep1, top_level=toplevel[1])
    mock_fetch.add_pkg_version(dep2, top_level=toplevel[2])

    await micropip.install(pkg)
    import json

    lockfile = json.loads(micropip.freeze())
    import pprint

    pprint.pprint(lockfile["packages"])
    pkg_metadata = lockfile["packages"][pkg]
    dep1_metadata = lockfile["packages"][dep1]
    dep2_metadata = lockfile["packages"][dep2]
    assert pkg_metadata["depends"] == [dep1, dep2]
    assert dep1_metadata["depends"] == []
    assert dep2_metadata["depends"] == []
    assert pkg_metadata["imports"] == toplevel[0]
    assert dep1_metadata["imports"] == toplevel[1]
    assert dep2_metadata["imports"] == toplevel[2]
