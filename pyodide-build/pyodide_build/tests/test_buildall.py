import argparse
import hashlib
import zipfile
from pathlib import Path
from time import sleep
from typing import Any

import pytest

from pyodide_build import buildall, io

RECIPE_DIR = Path(__file__).parent / "_test_recipes"


def test_generate_dependency_graph():
    # beautifulsoup4 has a circular dependency on soupsieve
    pkg_map = buildall.generate_dependency_graph(RECIPE_DIR, {"beautifulsoup4"})
    assert pkg_map["beautifulsoup4"].run_dependencies == ["soupsieve"]
    assert pkg_map["beautifulsoup4"].host_dependencies == []
    assert pkg_map["beautifulsoup4"].host_dependents == set()


@pytest.mark.parametrize(
    "in_set, out_set",
    [
        ({"scipy"}, {"scipy", "numpy", "CLAPACK"}),
        ({"scipy", "!numpy"}, set()),
        ({"scipy", "!numpy", "CLAPACK"}, {"CLAPACK"}),
        ({"scikit-learn", "!numpy"}, set()),
        ({"scikit-learn", "scipy", "!joblib"}, {"scipy", "numpy", "CLAPACK"}),
        ({"scikit-learn", "no-numpy-dependents"}, set()),
        ({"scikit-learn", "no-numpy-dependents", "numpy"}, {"numpy"}),
    ],
)
def test_generate_dependency_graph2(in_set, out_set):
    pkg_map = buildall.generate_dependency_graph(RECIPE_DIR, in_set)
    assert set(pkg_map.keys()) == out_set


def test_generate_dependency_graph_disabled(monkeypatch):
    class MockMetaConfig(io.MetaConfig):
        @classmethod
        def from_yaml(cls, path):
            d = io.MetaConfig.from_yaml(path)
            if "numpy" in str(path):
                d.package.disabled = True
            return d

    monkeypatch.setattr(buildall, "MetaConfig", MockMetaConfig)
    pkg_map = buildall.generate_dependency_graph(RECIPE_DIR, {"scipy"})
    assert set(pkg_map.keys()) == set()


def test_generate_repodata(tmp_path):
    pkg_map = buildall.generate_dependency_graph(
        RECIPE_DIR, {"pkg_1", "pkg_2", "libtest", "libtest_shared"}
    )
    hashes = {}
    for pkg in pkg_map.values():
        pkg.file_name = pkg.file_name or pkg.name + ".whl"
        # Write dummy package file for SHA-256 hash verification
        with zipfile.ZipFile(tmp_path / pkg.file_name, "w") as whlzip:
            whlzip.writestr(pkg.file_name, data=pkg.file_name)

        with open(tmp_path / pkg.file_name, "rb") as f:
            hashes[pkg.name] = hashlib.sha256(f.read()).hexdigest()

    package_data = buildall.generate_repodata(tmp_path, pkg_map)
    assert set(package_data.keys()) == {"info", "packages"}
    assert set(package_data["info"].keys()) == {"arch", "platform", "version", "python"}
    assert package_data["info"]["arch"] == "wasm32"
    assert package_data["info"]["platform"].startswith("emscripten")

    assert set(package_data["packages"]) == {
        "pkg_1",
        "pkg_1_1",
        "pkg_2",
        "pkg_3",
        "pkg_3_1",
        "libtest_shared",
    }
    assert package_data["packages"]["pkg_1"] == {
        "name": "pkg_1",
        "version": "1.0.0",
        "file_name": "pkg_1.whl",
        "depends": ["pkg_1_1", "pkg_3", "libtest_shared"],
        "imports": ["pkg_1"],
        "install_dir": "site",
        "sha256": hashes["pkg_1"],
    }

    sharedlib_imports = package_data["packages"]["libtest_shared"]["imports"]
    assert not sharedlib_imports, (
        "shared libraries should not have any imports, but got " f"{sharedlib_imports}"
    )


@pytest.mark.parametrize("n_jobs", [1, 4])
def test_build_dependencies(n_jobs, monkeypatch):
    build_list = []

    class MockPackage(buildall.Package):
        def build(self, args: Any) -> None:
            build_list.append(self.name)

    monkeypatch.setattr(buildall, "Package", MockPackage)

    pkg_map = buildall.generate_dependency_graph(RECIPE_DIR, {"pkg_1", "pkg_2"})

    buildall.build_from_graph(
        pkg_map, argparse.Namespace(n_jobs=n_jobs, force_rebuild=True)
    )

    assert set(build_list) == {
        "pkg_1",
        "pkg_1_1",
        "pkg_2",
        "pkg_3",
        "pkg_3_1",
        "libtest_shared",
    }
    assert build_list.index("pkg_1_1") < build_list.index("pkg_1")
    assert build_list.index("pkg_3") < build_list.index("pkg_1")
    assert build_list.index("pkg_3_1") < build_list.index("pkg_3")


@pytest.mark.parametrize("n_jobs", [1, 4])
def test_build_all_dependencies(n_jobs, monkeypatch):
    """Try building all the dependency graph, without the actual build operations"""

    class MockPackage(buildall.Package):
        n_builds = 0

        def build(self, args: Any) -> None:
            sleep(0.005)
            self.n_builds += 1
            # check that each build is only run once
            assert self.n_builds == 1

    monkeypatch.setattr(buildall, "Package", MockPackage)

    pkg_map = buildall.generate_dependency_graph(RECIPE_DIR, packages={"*"})

    buildall.build_from_graph(
        pkg_map, argparse.Namespace(n_jobs=n_jobs, force_rebuild=False)
    )


@pytest.mark.parametrize("n_jobs", [1, 4])
def test_build_error(n_jobs, monkeypatch):
    """Try building all the dependency graph, without the actual build operations"""

    class MockPackage(buildall.Package):
        def build(self, args: Any) -> None:
            raise ValueError("Failed build")

    monkeypatch.setattr(buildall, "Package", MockPackage)

    pkg_map = buildall.generate_dependency_graph(RECIPE_DIR, {"pkg_1"})

    with pytest.raises(ValueError, match="Failed build"):
        buildall.build_from_graph(
            pkg_map, argparse.Namespace(n_jobs=n_jobs, force_rebuild=True)
        )


def test_requirements_executable(monkeypatch):
    import shutil

    with monkeypatch.context() as m:
        m.setattr(shutil, "which", lambda exe: None)

        with pytest.raises(RuntimeError, match="missing in the host system"):
            buildall.generate_dependency_graph(RECIPE_DIR, {"pkg_test_executable"})

    with monkeypatch.context() as m:
        m.setattr(shutil, "which", lambda exe: "/bin")

        buildall.generate_dependency_graph(RECIPE_DIR, {"pkg_test_executable"})
