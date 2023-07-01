import os
import sys
from pathlib import Path

from .. import build_env, common, pypabuild
from ..io import _BuildSpecExports
from ..logger import logger


def default_exports() -> _BuildSpecExports:
    if "PYODIDE_EXPORTS" not in os.environ:
        return "requested"
    exports = os.environ["PYODIDE_EXPORTS"]
    if exports == "pyinit":
        return "pyinit"
    if exports == "requested":
        return "requested"
    if exports == "whole_archive":
        return "whole_archive"
    logger.stderr(
        'Expected PYODIDE_EXPORTS to be one of "pyinit", "requested", or"whole_archive" '
        f"Got {exports}"
    )
    sys.exit(1)


def run(
    srcdir: Path, outdir: Path, exports: _BuildSpecExports | None, args: list[str]
) -> Path:
    if exports is None:
        real_exports = default_exports()
    else:
        real_exports = exports

    outdir = outdir.resolve()
    cflags = build_env.get_build_flag("SIDE_MODULE_CFLAGS")
    cflags += f" {os.environ.get('CFLAGS', '')}"
    cxxflags = build_env.get_build_flag("SIDE_MODULE_CXXFLAGS")
    cxxflags += f" {os.environ.get('CXXFLAGS', '')}"
    ldflags = build_env.get_build_flag("SIDE_MODULE_LDFLAGS")
    ldflags += f" {os.environ.get('LDFLAGS', '')}"
    env = os.environ.copy()
    env.update(build_env.get_build_environment_vars())

    build_env_ctx = pypabuild.get_build_env(
        env=env,
        pkgname="",
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir="",
        exports=real_exports,
    )

    with build_env_ctx as env:
        built_wheel = pypabuild.build(srcdir, outdir, env, " ".join(args))

    wheel_path = Path(built_wheel)
    with common.modify_wheel(wheel_path) as wheel_dir:
        build_env.replace_so_abi_tags(wheel_dir)

    return wheel_path
