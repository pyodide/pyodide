from collections import namedtuple
from time import sleep

from pathlib import Path

from pyodide_build import buildall
import pytest

PACKAGES_DIR = (Path(__file__).parents[3] / "packages").resolve()


def test_generate_dependency_graph():
    pkg_map = buildall.generate_dependency_graph(PACKAGES_DIR, {"beautifulsoup4"})

    assert set(pkg_map.keys()) == {
        "soupsieve",
        "beautifulsoup4",
    }
    assert pkg_map["soupsieve"].dependencies == []
    assert pkg_map["soupsieve"].dependents == {"beautifulsoup4"}
    assert pkg_map["beautifulsoup4"].dependencies == ["soupsieve"]
    assert pkg_map["beautifulsoup4"].dependents == set()


def test_generate_packages_json():
    pkg_map = buildall.generate_dependency_graph(
        PACKAGES_DIR, {"beautifulsoup4", "micropip"}
    )

    package_data = buildall.generate_packages_json(pkg_map)
    assert set(package_data.keys()) == {"info", "packages"}
    assert package_data["info"] == {"arch": "wasm32", "platform": "Emscripten-1.0"}
    assert set(package_data["packages"]) == {
        "test",
        "distutils",
        "pyparsing",
        "packaging",
        "soupsieve",
        "beautifulsoup4",
        "micropip",
    }
    assert package_data["packages"]["micropip"] == {
        "name": "micropip",
        "version": "0.1",
        "depends": ["pyparsing", "packaging", "distutils"],
        "imports": ["micropip"],
    }


@pytest.mark.parametrize("n_jobs", [1, 4])
def test_build_dependencies(n_jobs, monkeypatch):
    build_list = []

    class MockPackage(buildall.Package):
        def build(self, outputdir: Path, args) -> None:
            build_list.append(self.name)

    monkeypatch.setattr(buildall, "Package", MockPackage)

    pkg_map = buildall.generate_dependency_graph(PACKAGES_DIR, {"lxml", "micropip"})

    Args = namedtuple("args", ["n_jobs", "force_rebuild"])
    buildall.build_from_graph(
        pkg_map, Path("."), Args(n_jobs=n_jobs, force_rebuild=True)
    )

    assert set(build_list) == {
        "packaging",
        "pyparsing",
        "soupsieve",
        "beautifulsoup4",
        "micropip",
        "webencodings",
        "html5lib",
        "cssselect",
        "lxml",
        "libxslt",
        "libxml",
        "zlib",
        "libiconv",
        "six",
    }
    assert build_list.index("pyparsing") < build_list.index("packaging")
    assert build_list.index("packaging") < build_list.index("micropip")
    assert build_list.index("soupsieve") < build_list.index("beautifulsoup4")


@pytest.mark.parametrize("n_jobs", [1, 4])
def test_build_all_dependencies(n_jobs, monkeypatch):
    """Try building all the dependency graph, without the actual build operations"""

    class MockPackage(buildall.Package):
        n_builds = 0

        def build(self, outputdir: Path, args) -> None:
            sleep(0.005)
            self.n_builds += 1
            # check that each build is only run once
            assert self.n_builds == 1

    monkeypatch.setattr(buildall, "Package", MockPackage)

    pkg_map = buildall.generate_dependency_graph(PACKAGES_DIR, packages={"*"})

    Args = namedtuple("args", ["n_jobs", "force_rebuild"])
    buildall.build_from_graph(
        pkg_map, Path("."), Args(n_jobs=n_jobs, force_rebuild=False)
    )


@pytest.mark.parametrize("n_jobs", [1, 4])
def test_build_error(n_jobs, monkeypatch):
    """Try building all the dependency graph, without the actual build operations"""

    class MockPackage(buildall.Package):
        def build(self, outputdir: Path, args) -> None:
            raise ValueError("Failed build")

    monkeypatch.setattr(buildall, "Package", MockPackage)

    pkg_map = buildall.generate_dependency_graph(PACKAGES_DIR, {"lxml"})

    with pytest.raises(ValueError, match="Failed build"):
        Args = namedtuple("args", ["n_jobs", "force_rebuild"])
        buildall.build_from_graph(
            pkg_map, Path("."), Args(n_jobs=n_jobs, force_rebuild=True)
        )
