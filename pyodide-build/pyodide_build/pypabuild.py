import json
import os
import shutil
import sys
import traceback
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from itertools import chain
from pathlib import Path
from tempfile import TemporaryDirectory

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

from . import common, pywasmcross
from .common import (
    environment_substitute_args,
    get_hostsitepackages,
    get_pyversion,
    get_unisolated_packages,
    replace_env,
)
from .io import _BuildSpecExports

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
            "setuptools<65.6.0",  # https://github.com/pypa/setuptools/issues/3693
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
            build_reqs = builder.get_requires_for_build(
                distribution,
            )
        except BuildBackendException:
            pass
        else:
            install_reqs(env, build_reqs)
            installed_requires_for_build = True

        with replace_env(build_env):
            if not installed_requires_for_build:
                install_reqs(
                    env,
                    builder.get_requires_for_build(
                        distribution,
                    ),
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


def make_command_wrapper_symlinks(symlink_dir: Path) -> dict[str, str]:
    """
    Create symlinks that make pywasmcross look like a compiler.

    Parameters
    ----------
    symlink_dir
        The directory where the symlinks will be created.

    Returns
    -------
    The dictionary of compiler environment variables that points to the symlinks.
    """

    pywasmcross_exe = symlink_dir / "pywasmcross.py"
    shutil.copy2(pywasmcross.__file__, pywasmcross_exe)
    pywasmcross_exe.chmod(0o755)

    env = {}
    for symlink in pywasmcross.SYMLINKS:
        symlink_path = symlink_dir / symlink
        if os.path.lexists(symlink_path) and not symlink_path.exists():
            # remove broken symlink so it can be re-created
            symlink_path.unlink()

        symlink_path.symlink_to(pywasmcross_exe)
        if symlink == "c++":
            var = "CXX"
        else:
            var = symlink.upper()
        env[var] = symlink

    return env


@contextmanager
def get_build_env(
    env: dict[str, str],
    *,
    pkgname: str,
    cflags: str,
    cxxflags: str,
    ldflags: str,
    target_install_dir: str,
    exports: _BuildSpecExports | list[_BuildSpecExports],
) -> Iterator[dict[str, str]]:
    """
    Returns a dict of environment variables that should be used when building
    a package with pypa/build.
    """

    kwargs = dict(
        pkgname=pkgname,
        cflags=cflags,
        cxxflags=cxxflags,
        ldflags=ldflags,
        target_install_dir=target_install_dir,
    )

    args = environment_substitute_args(kwargs, env)
    args["builddir"] = str(Path(".").absolute())
    args["exports"] = exports
    env = env.copy()

    with TemporaryDirectory() as symlink_dir_str:
        symlink_dir = Path(symlink_dir_str)
        env.update(make_command_wrapper_symlinks(symlink_dir))

        sysconfig_dir = Path(os.environ["TARGETINSTALLDIR"]) / "sysconfigdata"
        args["PYTHONPATH"] = sys.path + [str(sysconfig_dir)]
        args["orig__name__"] = __name__
        args["pythoninclude"] = os.environ["PYTHONINCLUDE"]
        args["PATH"] = env["PATH"]

        pywasmcross_env = json.dumps(args)
        # Store into environment variable and to disk. In most cases we will
        # load from the environment variable but if some other tool filters
        # environment variables we will load from disk instead.
        env["PYWASMCROSS_ARGS"] = pywasmcross_env
        (symlink_dir / "pywasmcross_env.json").write_text(pywasmcross_env)

        env["PATH"] = f"{symlink_dir}:{env['PATH']}"
        env["_PYTHON_HOST_PLATFORM"] = common.platform()
        env["_PYTHON_SYSCONFIGDATA_NAME"] = os.environ["SYSCONFIG_NAME"]
        env["PYTHONPATH"] = str(sysconfig_dir)
        yield env


def build(
    build_env: Mapping[str, str], backend_flags: str, outdir: str | None = None
) -> str:
    srcdir = Path.cwd()
    if outdir is None:
        outdir = str(srcdir / "dist")
    builder = _ProjectBuilder(str(srcdir))
    distribution = "wheel"
    config_settings = parse_backend_flags(backend_flags)
    try:
        with _handle_build_error():
            built = _build_in_isolated_env(
                build_env, builder, outdir, distribution, config_settings
            )
            print("{bold}{green}Successfully built {}{reset}".format(built, **_STYLES))
            return built
    except Exception as e:  # pragma: no cover
        tb = traceback.format_exc().strip("\n")
        print("\n{dim}{}{reset}\n".format(tb, **_STYLES))
        _error(str(e))
        sys.exit(1)
