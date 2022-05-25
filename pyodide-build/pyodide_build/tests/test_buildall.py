from collections import namedtuple
from pathlib import Path
from time import sleep
from typing import Any

import pytest

from pyodide_build import buildall

PACKAGES_DIR = Path(__file__).parent / "_test_packages"


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


def test_generate_packages_json(tmp_path):
    pkg_map = buildall.generate_dependency_graph(PACKAGES_DIR, {"pkg_1", "pkg_2"})
    for pkg in pkg_map.values():
        pkg.file_name = pkg.file_name or pkg.name + ".file"
        # Write dummy package file for SHA-256 hash verification
        with open(tmp_path / pkg.file_name, "w") as f:
            f.write(pkg.name)

    package_data = buildall.generate_packages_json(tmp_path, pkg_map)
    assert set(package_data.keys()) == {"info", "packages"}
    assert package_data["info"] == {"arch": "wasm32", "platform": "Emscripten-1.0"}
    assert set(package_data["packages"]) == {
        "pkg_1",
        "pkg_1_1",
        "pkg_2",
        "pkg_3",
        "pkg_3_1",
    }
    assert package_data["packages"]["pkg_1"] == {
        "name": "pkg_1",
        "version": "1.0.0",
        "file_name": "pkg_1.file",
        "depends": ["pkg_1_1", "pkg_3"],
        "imports": ["pkg_1"],
        "install_dir": "site",
        "sha256": "c1e38241013b5663e902fff97eb8585e98e6df446585da1dcf2ad121b52c2143",
    }


@pytest.mark.parametrize("n_jobs", [1, 4])
def test_build_dependencies(n_jobs, monkeypatch):
    build_list = []

    class MockPackage(buildall.Package):
        def build(self, outputdir: Path, args: Any) -> None:
            build_list.append(self.name)

    monkeypatch.setattr(buildall, "Package", MockPackage)

    pkg_map = buildall.generate_dependency_graph(PACKAGES_DIR, {"pkg_1", "pkg_2"})

    Args = namedtuple("Args", ["n_jobs", "force_rebuild"])
    buildall.build_from_graph(
        pkg_map, Path("."), Args(n_jobs=n_jobs, force_rebuild=True)
    )

    assert set(build_list) == {
        "pkg_1",
        "pkg_1_1",
        "pkg_2",
        "pkg_3",
        "pkg_3_1",
    }
    assert build_list.index("pkg_1_1") < build_list.index("pkg_1")
    assert build_list.index("pkg_3") < build_list.index("pkg_1")
    assert build_list.index("pkg_3_1") < build_list.index("pkg_3")


@pytest.mark.parametrize("n_jobs", [1, 4])
def test_build_all_dependencies(n_jobs, monkeypatch):
    """Try building all the dependency graph, without the actual build operations"""

    class MockPackage(buildall.Package):
        n_builds = 0

        def build(self, outputdir: Path, args: Any) -> None:
            sleep(0.005)
            self.n_builds += 1
            # check that each build is only run once
            assert self.n_builds == 1

    monkeypatch.setattr(buildall, "Package", MockPackage)

    pkg_map = buildall.generate_dependency_graph(PACKAGES_DIR, packages={"*"})

    Args = namedtuple("Args", ["n_jobs", "force_rebuild"])
    buildall.build_from_graph(
        pkg_map, Path("."), Args(n_jobs=n_jobs, force_rebuild=False)
    )


@pytest.mark.parametrize("n_jobs", [1, 4])
def test_build_error(n_jobs, monkeypatch):
    """Try building all the dependency graph, without the actual build operations"""

    class MockPackage(buildall.Package):
        def build(self, outputdir: Path, args: Any) -> None:
            raise ValueError("Failed build")

    monkeypatch.setattr(buildall, "Package", MockPackage)

    pkg_map = buildall.generate_dependency_graph(PACKAGES_DIR, {"pkg_1"})

    with pytest.raises(ValueError, match="Failed build"):
        Args = namedtuple("Args", ["n_jobs", "force_rebuild"])
        buildall.build_from_graph(
            pkg_map, Path("."), Args(n_jobs=n_jobs, force_rebuild=True)
        )
