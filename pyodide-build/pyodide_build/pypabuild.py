import contextlib
import os
import sys
import traceback
from itertools import chain
from pathlib import Path
from typing import Mapping

from build import BuildBackendException, ProjectBuilder  # type: ignore[import]
from build.__main__ import (  # type: ignore[import]
    _STYLES,
    _error,
    _handle_build_error,
    _IsolatedEnvBuilder,
    _ProjectBuilder,
)
from build.env import IsolatedEnv  # type: ignore[import]
from packaging.requirements import Requirement

from .common import get_hostsitepackages, get_pyversion

UNISOLATED_PACKAGES = ["numpy", "scipy", "cffi", "pycparser", "pythran", "cython"]


def symlink_unisolated_packages(env: IsolatedEnv):
    pyversion = get_pyversion()
    site_packages_path = f"lib/{pyversion}/site-packages"
    env_site_packages = Path(env._path) / site_packages_path
    host_site_packages = Path(get_hostsitepackages())
    for name in UNISOLATED_PACKAGES:
        for path in chain(
            host_site_packages.glob(f"{name}*"), host_site_packages.glob(f"_{name}*")
        ):
            (env_site_packages / path.name).unlink(missing_ok=True)
            (env_site_packages / path.name).symlink_to(path)


def remove_unisolated_requirements(requires: set[str]) -> set[str]:
    for reqstr in list(requires):
        req = Requirement(reqstr)
        for avoid_name in UNISOLATED_PACKAGES:
            if avoid_name in req.name:
                requires.remove(reqstr)
    return requires


@contextlib.contextmanager
def replace_env(build_env: Mapping[str, str]):
    old_environ = dict(os.environ)
    os.environ.clear()
    os.environ.update(build_env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_environ)


def install_reqs(env: IsolatedEnv, reqs: set[str]):
    env.install(remove_unisolated_requirements(reqs))


def _build_in_isolated_env(
    build_env: Mapping[str, str],
    builder: ProjectBuilder,
    outdir: str,
    distribution: str,
) -> str:
    with _IsolatedEnvBuilder() as env:
        builder.python_executable = env.executable
        builder.scripts_dir = env.scripts_dir
        # first install the build dependencies
        symlink_unisolated_packages(env)
        install_reqs(env, builder.build_system_requires)
        installed_requires_for_build = False
        try:
            build_reqs = builder.get_requires_for_build(distribution)
        except BuildBackendException:
            pass
        else:
            install_reqs(env, build_reqs)
            installed_requires_for_build = True

        with replace_env(build_env):
            if not installed_requires_for_build:
                install_reqs(env, builder.get_requires_for_build(distribution))
            return builder.build(distribution, outdir, {})


def build(build_env: Mapping[str, str]):
    srcdir = Path.cwd()
    outdir = srcdir / "dist"
    builder = _ProjectBuilder(srcdir)
    distribution = "wheel"
    try:
        with _handle_build_error():
            built = _build_in_isolated_env(
                build_env, builder, str(outdir), distribution
            )
            print("{bold}{green}Successfully built {}{reset}".format(built, **_STYLES))
    except Exception as e:  # pragma: no cover
        tb = traceback.format_exc().strip("\n")
        print("\n{dim}{}{reset}\n".format(tb, **_STYLES))
        _error(str(e))
        sys.exit(1)
