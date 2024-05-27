from typing import Literal

from pyodide_build.out_of_tree import build

# flake8: noqa
from .fixture import (
    dummy_xbuildenv,
    dummy_xbuildenv_url,
    reset_env_vars,
    reset_cache,
)

# selenium fixture b/c we can't run this test until after building Python.


def test_non_platformed_build(dummy_xbuildenv, tmp_path):
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
    exports: Literal["pyinit"] = "pyinit"
    config_settings = {}  # type:ignore[var-annotated]
    build.run(src, dst, exports, config_settings)

    wheels = list(dst.glob("*.whl"))
    assert len(wheels) == 1
    assert wheels[0].name == "fake_pkg-1.0-py3-none-any.whl"
