from pyodide_build.out_of_tree import build


def test_non_platformed_build(tmp_path):
    """Check that we don't accidentally attach Pyodide platform to non
    platformed wheels.
    """

    (tmp_path / "pyproject.toml").write_text(
        """\
[build-system]
build-backend = "hatchling.build"
requires = ["hatchling<1.22"]

[project]
requires-python = ">=3.10"
name = "fake-pkg"
version = "1.0"

[tool.hatch.build.targets.wheel]
packages = ["fake_pkg"]
        """
    )
    (tmp_path / "fake_pkg.py").write_text("print('hi from fake_pkg!')")
    src = tmp_path
    dst = tmp_path / "dist"
    exports = "pyinit"
    config_settings = {}
    build.run(src, dst, exports, config_settings)

    wheels = list(dst.glob("*.whl"))
    assert len(wheels) == 1
    assert wheels[0].name == "fake_pkg-1.0-py3-none-any.whl"
