import os
from pathlib import Path
from typing import Any

from .. import common, pypabuild, pywasmcross


def run(exports: Any, args: list[str], outdir: Path | None = None) -> Path:
    if outdir is None:
        outdir = Path("./dist")
    cflags = common.get_make_flag("SIDE_MODULE_CFLAGS")
    cflags += f" {os.environ.get('CFLAGS', '')}"
    cxxflags = common.get_make_flag("SIDE_MODULE_CXXFLAGS")
    cxxflags += f" {os.environ.get('CXXFLAGS', '')}"
    ldflags = common.get_make_flag("SIDE_MODULE_LDFLAGS")
    ldflags += f" {os.environ.get('LDFLAGS', '')}"

    build_env_ctx = pywasmcross.get_build_env(
        env=os.environ.copy(),
        pkgname="",
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir="",
        exports=exports,
    )

    with build_env_ctx as env:
        built_wheel = pypabuild.build(env, " ".join(args), outdir=str(outdir))
    return Path(built_wheel)
