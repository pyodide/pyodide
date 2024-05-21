import os
from pathlib import Path

from build import ConfigSettingsType

from .. import build_env, common, pypabuild
from ..build_env import get_pyodide_root, wheel_platform
from ..io import _BuildSpecExports


def run(
    srcdir: Path,
    outdir: Path,
    exports: _BuildSpecExports,
    config_settings: ConfigSettingsType,
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
    env.update(build_env.get_build_environment_vars(get_pyodide_root()))

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
        built_wheel = pypabuild.build(srcdir, outdir, env, config_settings)

    wheel_path = Path(built_wheel)
    wheel_path = common.retag_wheel(wheel_path, wheel_platform())
    with common.modify_wheel(wheel_path) as wheel_dir:
        build_env.replace_so_abi_tags(wheel_dir)

    return wheel_path
