from collections import namedtuple
from time import sleep

from pathlib import Path

from pyodide_build import buildall
import pytest

PACKAGES_DIR = (Path(__file__) / ".." / ".." / ".." / "packages").resolve()


def test_generate_dependency_graph():
    package_list = "beautifulsoup4"

    pkg_map = buildall.generate_dependency_graph(PACKAGES_DIR, package_list)

    assert set(pkg_map.keys()) == {"distlib", "soupsieve", "beautifulsoup4", "micropip"}
    assert pkg_map["soupsieve"].dependencies == []
    assert pkg_map["soupsieve"].dependents == {"beautifulsoup4"}
    assert pkg_map["beautifulsoup4"].dependencies == ["soupsieve"]
    assert pkg_map["beautifulsoup4"].dependents == set()


def test_build_dependencies():
    build_list = []

    class MockPackage(buildall.Package):
        def build(self, outputdir: Path, args) -> None:
            build_list.append(self.name)

    packages = {"micropip", "distlib", "soupsieve", "beautifulsoup4"}
    pkg_map = {}
    for pkg in packages:
        pkg_map[pkg] = MockPackage(PACKAGES_DIR / pkg)

    pkg_map["distlib"].dependents.add("micropip")
    pkg_map["soupsieve"].dependents.add("beautifulsoup4")

    Args = namedtuple("args", ["n_jobs"])
    buildall.build_from_graph(pkg_map, Path("."), Args(n_jobs=1))

    assert set(build_list) == packages
    assert build_list.index("distlib") < build_list.index("micropip")
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

    pkg_map = buildall.generate_dependency_graph(PACKAGES_DIR, package_list=None)

    Args = namedtuple("args", ["n_jobs"])
    buildall.build_from_graph(pkg_map, Path("."), Args(n_jobs=n_jobs))
