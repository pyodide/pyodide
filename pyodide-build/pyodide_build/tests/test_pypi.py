import os
import re
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from textwrap import dedent
from threading import Event, Thread
from typing import Any

import pytest
from build import ProjectBuilder
from typer.testing import CliRunner  # type: ignore[import]

from pyodide_build import __version__ as pyodide_build_version
from pyodide_build.cli import build
from pyodide_build.common import chdir

runner = CliRunner()


def _make_fake_package(
    root: Path, name: str, ver: str, requires: list[str], wheel: bool
) -> None:
    canonical_name = re.sub("[_.]", "-", name)
    module_name = re.sub("-", "_", name)
    packageDir = root / canonical_name
    packageDir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        build_path = Path(td)
        src_path = Path(td) / "src" / module_name
        src_path.mkdir(exist_ok=True, parents=True)
        with open(build_path / "pyproject.toml", "w") as cf:
            requirements = []
            extras_requirements: dict[str, list[str]] = {}
            for x in requires:
                extras = []
                if x.find(";") != -1:
                    requirement, marker_part = x.split(";")
                    extras = re.findall(r"extra\s*==\s*[\"'](\w+)[\"']", marker_part)
                else:
                    requirement = x
                if len(extras) > 0:
                    for match in extras:
                        if match not in extras_requirements:
                            extras_requirements[match] = []
                        extras_requirements[match].append(requirement)
                else:
                    requirements.append(requirement)
            extras_requirements_text = ""
            for e in extras_requirements.keys():
                extras_requirements_text += f"{e} = [\n"
                for r in extras_requirements[e]:
                    extras_requirements_text += f"'{r}',\n"
                extras_requirements_text += "]\n"
            template = dedent(
                """
                [build-system]
                build-backend = "setuptools.build_meta"
                requires = ["setuptools >= 65.0","wheel","cython >= 0.29.0"]

                [project]
                name = "{name}"
                version = "{version}"
                authors = [{{name = "Your Name", email = "you@yourdomain.com"}}]
                description = "Example project {name}"
                readme = "README.md"
                requires-python = ">=3.8"
                classifiers = [
                    "Development Status :: 3 - Alpha",
                    "License :: OSI Approved :: MIT License",
                    "Natural Language :: English",
                    "Operating System :: OS Independent",
                    "Programming Language :: Python",
                    "Programming Language :: Python :: 3.8",
                    "Programming Language :: Python :: 3.9",
                ]
                dependencies = {requirements}
                [project.optional-dependencies]
                {optional_deps_text}
                """
            )
            config_str = template.format(
                name=canonical_name,
                version=ver,
                requirements=str(requirements),
                optional_deps_text=extras_requirements_text,
            )
            cf.write(config_str)
        with open(build_path / "README.md", "w") as rf:
            rf.write("\n")
        if wheel:
            with open(src_path / "__init__.py", "w") as f:
                f.write(f'print("Hello from {name} module")\n')

            builder = ProjectBuilder(srcdir=build_path)
            builder.build(distribution="wheel", output_directory=packageDir)
        else:
            # make cython sdist
            # i.e. create pyc + setup.cfg (needs cython) in folder and run python -m build
            with open(src_path / "__init__.py", "w") as f:
                f.write("from .compiled_mod import *")
            with open(src_path / "compiled_mod.pyx", "w") as f:
                f.write(f'print("Hello from compiled module {name}")')
            with open(build_path / "setup.py", "w") as sf:
                sf.write(
                    f'from setuptools import setup\nfrom Cython.Build import cythonize\nsetup(ext_modules=cythonize("src/{module_name}/*.pyx"))'
                )
            with open(build_path / "MANIFEST.in", "w") as mf:
                mf.write("global-include *.pyx")
            builder = ProjectBuilder(srcdir=build_path)
            builder.build(distribution="sdist", output_directory=packageDir)


# module scope fixture that makes a fake pypi
@pytest.fixture(scope="module")
def fake_pypi_server():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        simple_root = root / "simple"
        simple_root.mkdir(exist_ok=True, parents=True)
        # top package resolves_package that should resolve okay
        _make_fake_package(
            simple_root, "resolves-package", "1.0.0", ["pkg-a", "pkg-b[docs]"], True
        )
        _make_fake_package(simple_root, "pkg-a", "1.0.0", ["pkg-c"], True)
        _make_fake_package(
            simple_root, "pkg-b", "1.0.0", ['pkg-d==2.0.0;extra=="docs"'], False
        )
        _make_fake_package(simple_root, "pkg-c", "1.0.0", [], True)
        _make_fake_package(simple_root, "pkg-c", "2.0.0", [], True)
        _make_fake_package(simple_root, "pkg-d", "1.0.0", [], False)
        _make_fake_package(simple_root, "pkg-d", "2.0.0", [], False)

        # top package doesn't resolve package that requires
        _make_fake_package(
            simple_root,
            "fails_package",
            "1.0.0",
            ["pkg_a", "pkg_b[docs]", "pkg_d==1.0.0"],
            True,
        )

        # spawn webserver
        def server_thread(
            root_path: Path, server_evt: Event, ret_values: list[Any]
        ) -> None:
            class PathRequestHandler(SimpleHTTPRequestHandler):
                def __init__(self, *args, **argv):
                    argv["directory"] = root_path
                    super().__init__(*args, **argv)

            server = ThreadingHTTPServer(("127.0.0.1", 0), PathRequestHandler)
            ret_values.append(server)
            server_evt.set()
            server.serve_forever(poll_interval=0.05)

        server_evt = Event()
        ret_values: list[ThreadingHTTPServer] = []
        running_thread = Thread(
            target=server_thread, args=(root, server_evt, ret_values)
        )
        running_thread.start()
        server_evt.wait()
        # now ret_values[0] should be server
        server = ret_values[0]
        addr = f"http://{server.server_address[0]}:{server.server_address[1]}/simple"

        yield (addr, f"{server.server_address[0]}:{server.server_address[1]}")
        # cleanup
        server.shutdown()


# fixture to redirect a single test to use fake pypi in resolution
@pytest.fixture
def fake_pypi_url(fake_pypi_server):
    import pyodide_build.out_of_tree.pypi

    pypi_old = pyodide_build.out_of_tree.pypi._PYPI_INDEX
    pyodide_build.out_of_tree.pypi._PYPI_TRUSTED_HOSTS = [fake_pypi_server[1]]
    pyodide_build.out_of_tree.pypi._PYPI_INDEX = [fake_pypi_server[0]]
    yield fake_pypi_server[0]
    pyodide_build.out_of_tree.pypi._PYPI_INDEX = pypi_old


def test_fetch_or_build_pypi(tmp_path):
    if "dev" in pyodide_build_version:
        if "EMSDK" not in os.environ or "PYODIDE_ROOT" not in os.environ:
            pytest.skip(
                reason="Can't build recipe in dev mode without building pyodide first. Skipping test"
            )
    output_dir = tmp_path / "dist"
    # one pure-python package (doesn't need building) and one sdist package (needs building)
    pkgs = ["pytest-pyodide", "pycryptodome==3.15.0"]

    os.chdir(tmp_path)
    for p in pkgs:
        result = runner.invoke(
            build.app,
            [p],
        )
        assert result.exit_code == 0, result.stdout

    built_wheels = set(output_dir.glob("*.whl"))
    assert len(built_wheels) == len(pkgs)


def test_fetch_or_build_pypi_with_deps_and_extras(tmp_path):
    if "dev" in pyodide_build_version:
        if "EMSDK" not in os.environ or "PYODIDE_ROOT" not in os.environ:
            pytest.skip(
                reason="Can't build recipe in dev mode without building pyodide first. Skipping test"
            )
    output_dir = tmp_path / "dist"
    # one pure-python package (doesn't need building) which depends on one sdist package (needs building)
    pkgs = ["eth-hash[pycryptodome]==0.5.1", "safe-pysha3 (>=1.0.0)"]

    os.chdir(tmp_path)
    for p in pkgs:
        result = runner.invoke(
            build.app,
            [p, "--build-dependencies"],
        )
        assert result.exit_code == 0, result.stdout

    built_wheels = set(output_dir.glob("*.whl"))
    assert len(built_wheels) == 3


def test_fake_pypi_succeed(tmp_path, fake_pypi_url):
    if "dev" in pyodide_build_version:
        if "EMSDK" not in os.environ or "PYODIDE_ROOT" not in os.environ:
            pytest.skip(
                reason="Can't build recipe in dev mode without building pyodide first. Skipping test"
            )
    output_dir = tmp_path / "dist"
    # build package that resolves right
    with chdir(tmp_path):
        result = runner.invoke(
            build.app,
            ["resolves-package", "--build-dependencies"],
        )

        assert result.exit_code == 0, str(result.stdout) + str(result)

    built_wheels = set(output_dir.glob("*.whl"))
    assert len(built_wheels) == 5


def test_fake_pypi_resolve_fail(tmp_path, fake_pypi_url):
    if "dev" in pyodide_build_version:
        if "EMSDK" not in os.environ or "PYODIDE_ROOT" not in os.environ:
            pytest.skip(
                reason="Can't build recipe in dev mode without building pyodide first. Skipping test"
            )
    output_dir = tmp_path / "dist"
    # build package that resolves right

    with chdir(tmp_path):
        result = runner.invoke(
            build.app,
            ["fails-package", "--build-dependencies"],
        )

    # this should fail
    assert result.exit_code != 0, result.stdout
    built_wheels = set(output_dir.glob("*.whl"))
    assert len(built_wheels) == 0


def test_fake_pypi_extras_build(tmp_path, fake_pypi_url):
    if "dev" in pyodide_build_version:
        if "EMSDK" not in os.environ or "PYODIDE_ROOT" not in os.environ:
            pytest.skip(
                reason="Can't build recipe in dev mode without building pyodide first. Skipping test"
            )
    output_dir = tmp_path / "dist"
    # build package that resolves right

    with chdir(tmp_path):
        result = runner.invoke(
            build.app,
            ["pkg-b[docs]", "--build-dependencies"],
        )

    # this should fail
    assert result.exit_code == 0, result.stdout
    built_wheels = set(output_dir.glob("*.whl"))
    assert len(built_wheels) == 2


@pytest.mark.parametrize(
    "fn", [test_fetch_or_build_pypi, test_fetch_or_build_pypi_with_deps_and_extras]
)
def test_host_in_node_test(runtime, fn, tmp_path):
    if runtime.startswith("node"):
        fn(tmp_path)


@pytest.mark.parametrize(
    "fn",
    [
        test_fake_pypi_succeed,
        test_fake_pypi_resolve_fail,
        test_fake_pypi_succeed,
        test_fake_pypi_extras_build,
    ],
)
def test_host_in_node_test_fake_pypi(runtime, fn, tmp_path, fake_pypi_url):
    if runtime.startswith("node"):
        fn(tmp_path, fake_pypi_url)
