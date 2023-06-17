import os
from pathlib import Path
from typing import Any

from .. import common, pypabuild


def run(srcdir: Path, outdir: Path, exports: Any, args: list[str]) -> Path:
    outdir = outdir.resolve()
    cflags = common.get_build_flag("SIDE_MODULE_CFLAGS")
    cflags += f" {os.environ.get('CFLAGS', '')}"
    cxxflags = common.get_build_flag("SIDE_MODULE_CXXFLAGS")
    cxxflags += f" {os.environ.get('CXXFLAGS', '')}"
    ldflags = common.get_build_flag("SIDE_MODULE_LDFLAGS")
    ldflags += f" {os.environ.get('LDFLAGS', '')}"
    env = os.environ.copy()
    env.update(common.get_build_environment_vars())

    build_env_ctx = pypabuild.get_build_env(
        env=env,
        pkgname="",
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir="",
        exports=exports,
    )

    with build_env_ctx as env:
        built_wheel = pypabuild.build(srcdir, outdir, env, " ".join(args))

    wheel_path = Path(built_wheel)
    with common.modify_wheel(wheel_path) as wheel_dir:
        common.replace_so_abi_tags(wheel_dir)

    return wheel_path
