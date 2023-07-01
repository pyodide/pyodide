import os
import sys
from pathlib import Path

from .. import build_env, common, pypabuild
from ..io import _BuildSpecExports
from ..logger import logger


def convert_exports(exports: str, source: str) -> _BuildSpecExports | list[str]:
    if "," in exports:
        return [x.strip() for x in exports.split(",")]
    if exports == "pyinit":
        return "pyinit"
    if exports == "requested":
        return "requested"
    if exports == "whole_archive":
        return "whole_archive"
    logger.stderr(
        f"Expected {source} to be one of "
        '"pyinit", "requested", "whole_archive", '
        "or an explicit list of names to export. "
        f'Got "{exports}".'
    )
    sys.exit(1)


def run(srcdir: Path, outdir: Path, exports: str | None, args: list[str]) -> Path:
    real_exports = None
    if exports:
        real_exports = convert_exports(exports, "--exports")
    if real_exports is None and "PYODIDE_EXPORTS" in os.environ:
        real_exports = convert_exports(os.environ["PYODIDE_EXPORTS"], "PYODIDE_EXPORTS")
    if real_exports is None:
        real_exports = "requested"

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
