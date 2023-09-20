import os
from pathlib import Path

from .. import build_env, common, pypabuild
from ..io import _BuildSpecExports


def run(
    srcdir: Path, outdir: Path, exports: _BuildSpecExports, args: list[str]
) -> Path:
    outdir = outdir.resolve()
    cflags = build_env.get_build_flag("SIDE_MODULE_CFLAGS")
    cflags += f" {os.environ.get('CFLAGS', '')}"
    cxxflags = build_env.get_build_flag("SIDE_MODULE_CXXFLAGS")
    cxxflags += f" {os.environ.get('CXXFLAGS', '')}"
    ldflags = build_env.get_build_flag("SIDE_MODULE_LDFLAGS")
    ldflags += f" {os.environ.get('LDFLAGS', '')}"
    target_install_dir = os.environ.get(
        "TARGETINSTALLDIR", build_env.get_build_flag("TARGETINSTALLDIR")
    )
    env = os.environ.copy()
    env.update(build_env.get_build_environment_vars())

    build_env_ctx = pypabuild.get_build_env(
        env=env,
        pkgname="",
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir=target_install_dir,
        exports=exports,
    )

    with build_env_ctx as env:
        built_wheel = pypabuild.build(srcdir, outdir, env, " ".join(args))

    wheel_path = Path(built_wheel)
    with common.modify_wheel(wheel_path) as wheel_dir:
        build_env.replace_so_abi_tags(wheel_dir)

    return wheel_path
