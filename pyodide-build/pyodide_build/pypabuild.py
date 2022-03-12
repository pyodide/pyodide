from pathlib import Path
from typing import Sequence

from build.env import IsolatedEnvBuilder  # type: ignore[import]
from packaging.requirements import Requirement

from build import ProjectBuilder  # type: ignore[import]

from .common import get_make_flag, get_pyversion

_COLORS = {
    "red": "\33[91m",
    "green": "\33[92m",
    "yellow": "\33[93m",
    "bold": "\33[1m",
    "dim": "\33[2m",
    "underline": "\33[4m",
    "reset": "\33[0m",
}
_STYLES = _COLORS


class _ProjectBuilder(ProjectBuilder):
    @staticmethod
    def log(message: str) -> None:
        print("{bold}* {}{reset}".format(message, **_STYLES))


class _IsolatedEnvBuilder(IsolatedEnvBuilder):
    @staticmethod
    def log(message: str) -> None:
        print("{bold}* {}{reset}".format(message, **_STYLES))

    def __exit__(self, *args):
        print("EXITING ISOLATED ENV!", self._path)


def unisolate_numpy_and_scipy(env, requires: set[str]) -> set[str]:
    for reqstr in list(requires):
        req = Requirement(reqstr)
        for avoid_name in ["scipy", "numpy"]:
            if avoid_name in req.name:
                requires.remove(reqstr)
    print("\n\nrequires", requires)
    print("\n\n")
    return requires


def symlink_unisolated_packages(env):
    pyversion = get_pyversion()
    site_packages_path = f"lib/{pyversion}/site-packages"
    env_site_packages = Path(env._path) / site_packages_path
    host_installdir = Path(get_make_flag("HOSTINSTALLDIR"))
    host_site_packages = host_installdir / site_packages_path
    for path in host_site_packages.glob("numpy*"):
        (env_site_packages / path.name).unlink(missing_ok=True)
        (env_site_packages / path.name).symlink_to(path)
    for path in host_site_packages.glob("scipy*"):
        (env_site_packages / path.name).unlink(missing_ok=True)
        (env_site_packages / path.name).symlink_to(path)


def _build_in_isolated_env(
    builder: ProjectBuilder, outdir, distribution: str, config_settings
):
    with _IsolatedEnvBuilder() as env:
        builder.python_executable = env.executable
        builder.scripts_dir = env.scripts_dir
        # first install the build dependencies
        symlink_unisolated_packages(env)
        env.install(unisolate_numpy_and_scipy(env, builder.build_system_requires))
        env.install(
            unisolate_numpy_and_scipy(env, builder.get_requires_for_build(distribution))
        )

        builder.build(distribution, outdir, config_settings or {})


def build_package(
    srcdir,
    outdir,
    distributions: Sequence[str],
    config_settings=None,
    skip_dependency_check: bool = False,
):
    """
    Run the build process.

    :param srcdir: Source directory
    :param outdir: Output directory
    :param distribution: Distribution to build (sdist or wheel)
    :param config_settings: Configuration settings to be passed to the backend
    :param isolation: Isolate the build in a separate environment
    :param skip_dependency_check: Do not perform the dependency check
    """
    builder = _ProjectBuilder(srcdir)
    for distribution in distributions:
        _build_in_isolated_env(builder, outdir, distribution, config_settings)


def build():
    srcdir = Path.cwd()
    outdir = srcdir / "dist"
    distributions = ["wheel"]
    build_package(srcdir, outdir, distributions)
