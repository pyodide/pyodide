import os
import shutil
import sys
import traceback
from collections.abc import Mapping
from itertools import chain
from pathlib import Path

from build import BuildBackendException, ConfigSettingsType, ProjectBuilder
from build.__main__ import (
    _STYLES,
    _error,
    _handle_build_error,
    _IsolatedEnvBuilder,
    _ProjectBuilder,
)
from build.env import IsolatedEnv
from packaging.requirements import Requirement

from .common import (
    get_hostsitepackages,
    get_pyversion,
    get_unisolated_packages,
    replace_env,
)

AVOIDED_REQUIREMENTS = [
    # We don't want to install cmake Python package inside the isolated env as it will shadow
    # the pywasmcross cmake wrapper.
    "cmake",
]


def symlink_unisolated_packages(env: IsolatedEnv) -> None:
    pyversion = get_pyversion()
    site_packages_path = f"lib/{pyversion}/site-packages"
    env_site_packages = Path(env.path) / site_packages_path  # type: ignore[attr-defined]
    sysconfigdata_name = os.environ["SYSCONFIG_NAME"]
    sysconfigdata_path = (
        Path(os.environ["TARGETINSTALLDIR"]) / f"sysconfigdata/{sysconfigdata_name}.py"
    )

    env_site_packages.mkdir(parents=True, exist_ok=True)
    shutil.copy(sysconfigdata_path, env_site_packages)
    host_site_packages = Path(get_hostsitepackages())
    for name in get_unisolated_packages():
        for path in chain(
            host_site_packages.glob(f"{name}*"), host_site_packages.glob(f"_{name}*")
        ):
            (env_site_packages / path.name).unlink(missing_ok=True)
            (env_site_packages / path.name).symlink_to(path)


def remove_avoided_requirements(
    requires: set[str], avoided_requirements: set[str] | list[str]
) -> set[str]:
    for reqstr in list(requires):
        req = Requirement(reqstr)
        for avoid_name in set(avoided_requirements):
            if avoid_name in req.name.lower():
                requires.remove(reqstr)
    return requires


def install_reqs(env: IsolatedEnv, reqs: set[str]) -> None:
    env.install(
        remove_avoided_requirements(
            reqs, get_unisolated_packages() + AVOIDED_REQUIREMENTS
        )
    )
    # Some packages (numcodecs) don't declare cython as a build dependency and
    # only recythonize if it is present. We need them to always recythonize so
    # we always install cython. If the reqs included some cython version already
    # then this won't do anything.
    env.install(
        [
            "cython",
            "pythran",
        ]
    )


def _build_in_isolated_env(
    build_env: Mapping[str, str],
    builder: ProjectBuilder,
    outdir: str,
    distribution: str,
    config_settings: ConfigSettingsType,
) -> str:
    # For debugging: The following line disables removal of the isolated venv.
    # It will be left in the /tmp folder and can be inspected or entered as
    # needed.
    # _IsolatedEnvBuilder.__exit__ = lambda *args: None
    with _IsolatedEnvBuilder() as env:
        builder.python_executable = env.executable
        builder.scripts_dir = env.scripts_dir
        # first install the build dependencies
        symlink_unisolated_packages(env)
        install_reqs(env, builder.build_system_requires)
        installed_requires_for_build = False
        try:
            build_reqs = builder.get_requires_for_build(distribution, config_settings)
        except BuildBackendException:
            pass
        else:
            install_reqs(env, build_reqs)
            installed_requires_for_build = True

        with replace_env(build_env):
            if not installed_requires_for_build:
                install_reqs(
                    env, builder.get_requires_for_build(distribution, config_settings)
                )
            return builder.build(distribution, outdir, config_settings)


def parse_backend_flags(backend_flags: str) -> ConfigSettingsType:
    config_settings: dict[str, str | list[str]] = {}
    for arg in backend_flags.split():
        setting, _, value = arg.partition("=")
        if setting not in config_settings:
            config_settings[setting] = value
            continue

        cur_value = config_settings[setting]
        if isinstance(cur_value, str):
            config_settings[setting] = [cur_value, value]
        else:
            cur_value.append(value)
    return config_settings


def build(build_env: Mapping[str, str], backend_flags: str) -> None:
    srcdir = Path.cwd()
    outdir = srcdir / "dist"
    builder = _ProjectBuilder(str(srcdir))
    distribution = "wheel"
    config_settings = parse_backend_flags(backend_flags)
    try:
        with _handle_build_error():
            built = _build_in_isolated_env(
                build_env, builder, str(outdir), distribution, config_settings
            )
            print("{bold}{green}Successfully built {}{reset}".format(built, **_STYLES))
    except Exception as e:  # pragma: no cover
        tb = traceback.format_exc().strip("\n")
        print("\n{dim}{}{reset}\n".format(tb, **_STYLES))
        _error(str(e))
        sys.exit(1)
