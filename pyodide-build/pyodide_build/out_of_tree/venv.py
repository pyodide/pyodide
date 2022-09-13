import argparse
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

from ..common import (
    check_emscripten_version,
    exit_with_stdio,
    get_make_flag,
    get_pyodide_root,
    in_xbuildenv,
)


def main(parser_args: argparse.Namespace) -> None:
    create_pyodide_venv(Path(parser_args.dest))


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = "Create a Pyodide virtual environment"
    parser.add_argument("dest", help="directory to create virtualenv at", type=str)
    return parser


def eprint(*args, **kwargs):
    """Print to stderr"""
    print(*args, **kwargs, file=sys.stderr)


def check_result(result: subprocess.CompletedProcess[str], msg: str) -> None:
    """Abort if the process returns a nonzero error code"""
    if result.returncode != 0:
        eprint(msg)
        exit_with_stdio(result)


def dedent(s: str) -> str:
    return textwrap.dedent(s).strip() + "\n"


def get_pyversion() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def check_host_python_version(session: Any) -> None:
    pyodide_version = session.interpreter.version.partition(" ")[0].split(".")[:2]
    sys_version = [str(sys.version_info.major), str(sys.version_info.minor)]
    if pyodide_version == sys_version:
        return
    pyodide_version_fmt = ".".join(pyodide_version)
    sys_version_fmt = ".".join(sys_version)
    eprint(
        f"Expected host Python version to be {pyodide_version_fmt} but got version {sys_version_fmt}"
    )
    sys.exit(1)


def create_pip_conf(venv_root: Path) -> None:
    """Create pip.conf file in venv root

    This file adds a few options that will always be used by pip install.
    """
    if in_xbuildenv():
        # In the xbuildenv, we don't have the packages locally. We will include
        # in the xbuildenv a PEP 503 index for the vendored Pyodide packages
        # https://peps.python.org/pep-0503/
        repo = f'extra-index-url=file:{get_pyodide_root()/"pypa_index"}'
    else:
        # In the Pyodide development environment, the Pyodide dist directory
        # should contain the needed wheels. find-links
        repo = f'find-links={get_pyodide_root()/"dist"}'

    # Prevent attempts to install binary wheels from source.
    # Maybe some day we can convince pip to invoke `pyodide build` as the build
    # front end for wheels...
    (venv_root / "pip.conf").write_text(
        dedent(
            f"""
            [install]
            only-binary=:all:
            {repo}
            """
        )
    )


def get_pip_monkeypatch(venv_bin: Path) -> str:
    """Monkey patch pip's environment to show info about Pyodide's environment.

    The code returned is injected at the beginning of the pip script.
    """
    result = subprocess.run(
        [
            venv_bin / "python",
            "-c",
            dedent(
                """
                import os, sys, sysconfig, platform
                print([
                    os.name,
                    sys.platform,
                    sys.implementation._multiarch,
                    sysconfig.get_platform()
                ])
                """
            ),
        ],
        capture_output=True,
        encoding="utf8",
    )
    check_result(result, "ERROR: failed to invoke Pyodide")
    platform_data = result.stdout
    sysconfigdata_dir = Path(get_make_flag("TARGETINSTALLDIR")) / "sysconfigdata"

    return dedent(
        f"""\
        import os
        import sys
        os_name, sys_platform, multiarch, host_platform = {platform_data}
        os.name = os_name
        sys.platform = sys_platform
        sys.implementation._multiarch = multiarch
        os.environ["_PYTHON_HOST_PLATFORM"] = host_platform
        os.environ["_PYTHON_SYSCONFIGDATA_NAME"] = f'_sysconfigdata_{{sys.abiflags}}_{{sys.platform}}_{{sys.implementation._multiarch}}'
        sys.path.append("{sysconfigdata_dir}")
        """
    )


def create_pip_script(venv_bin):
    """Create pip and write it into the virtualenv bin folder."""
    # pip needs to run in the host Python not in Pyodide, so we'll use the host
    # Python in the shebang. Use whichever Python was used to invoke
    # pyodide venv.
    host_python_path = venv_bin / f"python{get_pyversion()}-host"
    host_python_path.symlink_to(sys.executable)

    (venv_bin / "pip").write_text(
        # Other than the shebang and the monkey patch, this is exactly what
        # normal pip looks like.
        f"#!{host_python_path} -s\n"
        + get_pip_monkeypatch(venv_bin)
        + dedent(
            """
            import re
            import sys
            from pip._internal.cli.main import main
            if __name__ == '__main__':
                sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])
                sys.exit(main())
            """
        )
    )
    (venv_bin / "pip").chmod(0o777)

    pyversion = get_pyversion()
    other_pips = [
        venv_bin / "pip3",
        venv_bin / f"pip{pyversion}",
        venv_bin / f"pip-{pyversion}",
    ]

    for pip in other_pips:
        pip.unlink()
        pip.symlink_to(venv_bin / "pip")


def create_pyodide_script(venv_bin: Path) -> None:
    """Write pyodide cli script into the virtualenv bin folder"""
    import os

    # The pyodide cli must be invoked outside of the virtual env. In order to
    # ensure this, we have to restore VIRTUAL_ENV, PATH, and PYODIDE_ROOT to
    # their current values before invoking it..
    # In case we are inside an xbuildenv, make sure to make the path relative to
    # this file and not relative to PYODIDE_ROOT.
    pyodide_build_path = str(Path(__file__).parents[2])

    # Resetting PATH and VIRTUAL_ENV will temporarily restore us to the virtual
    # environment that 'pyodide venv' was invoked in (or no virtual environment
    # if we aren't currently in one). To be extra careful, we set PYTHON_PATH too.
    environment_vars = [f"PYTHONPATH={pyodide_build_path}"]
    for environment_var in ["VIRTUAL_ENV", "PATH", "PYODIDE_ROOT"]:
        value = os.environ.get(environment_var, "''")
        environment_vars.append(f"{environment_var}={value}")
    environment = " ".join(environment_vars)

    pyodide_path = venv_bin / "pyodide"
    pyodide_path.write_text(
        dedent(
            f"""
            #!/bin/sh
            {environment} exec {sys.executable} -m pyodide_build.out_of_tree "$@"
            """
        )
    )
    pyodide_path.chmod(0o777)


def install_stdlib(venv_bin: Path) -> None:
    """Install micropip and all unvendored stdlib modules"""
    # Micropip we could install with pip hypothetically, but because we use
    # `--extra-index-url` it would install the pypi version which we don't want.

    # Other stuff we need to load with loadPackage
    # TODO: Also load all shared libs.
    to_load = ["micropip"]
    result = subprocess.run(
        [
            venv_bin / "python",
            "-c",
            dedent(
                f"""
                from _pyodide._importhook import UNVENDORED_STDLIBS_AND_TEST;
                from pyodide_js import loadPackage;

                to_load = [*UNVENDORED_STDLIBS_AND_TEST, *{to_load!r}]
                loadPackage(to_load);
                """
            ),
        ],
        capture_output=True,
        encoding="utf8",
    )
    check_result(result, "ERROR: failed to install unvendored stdlib modules")


def create_pyodide_venv(dest: Path) -> None:
    """Create a Pyodide virtualenv and store it into dest"""
    print("Creating Pyodide virtualenv at", str(dest))
    from virtualenv import session_via_cli  # type: ignore[import]

    if dest.exists():
        eprint(f"ERROR: dest directory '{dest}' already exists")
        sys.exit(1)

    check_emscripten_version()

    pyodide_root = get_pyodide_root()
    interp_path = pyodide_root / "tools/python"
    session = session_via_cli(["--no-wheel", "-p", str(interp_path), str(dest)])
    check_host_python_version(session)

    try:
        session.run()
        venv_root = Path(session.creator.dest).absolute()
        venv_bin = venv_root / "bin"

        print("... Configuring virtualenv")
        create_pip_conf(venv_root)
        create_pip_script(venv_bin)
        create_pyodide_script(venv_bin)
        print("... Installing standard library")
        install_stdlib(venv_bin)
    except (Exception, KeyboardInterrupt, SystemExit):
        shutil.rmtree(session.creator.dest)
        raise

    print("Successfully created Pyodide virtual environment!")
