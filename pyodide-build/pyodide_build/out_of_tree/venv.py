import argparse
import subprocess
import sys
import textwrap
from pathlib import Path

from ..common import (
    check_emscripten_version,
    exit_with_stdio,
    get_make_flag,
    get_pyodide_root,
    in_xbuild_env,
)


def main(parser_args: argparse.Namespace) -> None:
    run(Path(parser_args.dest))


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = "Create a Pyodide virtual environment"
    parser.add_argument("dest", help="directory to create virtualenv at", type=str)
    return parser


def dedent(s):
    return textwrap.dedent(s).strip() + "\n"


def run(dest: Path) -> None:
    print("Creating Pyodide virtualenv")
    from virtualenv import session_via_cli  # type: ignore[import]

    if dest.exists():
        print(f"dest directory '{dest}' already exists", file=sys.stderr)
        sys.exit(1)

    check_emscripten_version()

    interp_path = get_pyodide_root() / "tools/python.js"
    version_major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    session = session_via_cli(["--no-wheel", "-p", str(interp_path), str(dest)])
    pyodide_version = session.interpreter.version.partition(" ")[0].split(".")
    if sys.version_info.major != int(
        pyodide_version[0]
    ) or sys.version_info.minor != int(pyodide_version[1]):
        expected_version = ".".join(pyodide_version[:2])
        print(
            f"Expected host Python version to be {expected_version} but got version {version_major_minor}",
            file=sys.stderr,
        )
        sys.exit(1)

    session.run()

    if in_xbuild_env():
        repo = f'extra-index-url={get_pyodide_root()/"dist/pypi_index"}'
    else:
        repo = f'find-links={get_pyodide_root()/"dist"}'

    dest = Path(session.creator.dest).absolute()
    (dest / "pip.conf").write_text(
        dedent(
            f"""
            [install]
            only-binary=:all:
            {repo}
            """
        )
    )

    bin = dest / "bin"

    host_python_path = bin / "python3.10-host"
    host_python_path.symlink_to(sys.executable)
    pip_path = bin / "pip"
    result = subprocess.run(
        [
            bin / "python",
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
    if result.returncode != 0:
        print("ERROR: failed to invoke Pyodide")
        exit_with_stdio(result)

    pymajor = get_make_flag("PYMAJOR")
    pyminor = get_make_flag("PYMINOR")
    pymicro = get_make_flag("PYMICRO")
    pyversion = f"python-{pymajor}.{pyminor}.{pymicro}"
    sysconfigdata_dir = (
        get_pyodide_root() / "cpython/installs" / pyversion / "sysconfigdata"
    )
    pip_path.write_text(
        dedent(
            f"""
            #!{host_python_path}
            # -*- coding: utf-8 -*-
            import os
            import sys

            posix = os
            os_name, sys_platform, multiarch, host_platform = {result.stdout}
            os.name = os_name
            sys.platform = sys_platform
            sys.implementation._multiarch = multiarch
            os.environ["_PYTHON_HOST_PLATFORM"] = host_platform
            os.environ["_PYTHON_SYSCONFIGDATA_NAME"] = f'_sysconfigdata_{{sys.abiflags}}_{{sys.platform}}_{{sys.implementation._multiarch}}'
            sys.path.append("{sysconfigdata_dir}")

            import re
            import sys
            from pip._internal.cli.main import main
            if __name__ == '__main__':
                sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])
                sys.exit(main())
            """
        )
    )
    pip_path.chmod(0o777)

    other_pips = [
        bin / "pip3",
        bin / f"pip{version_major_minor}",
        bin / f"pip-{version_major_minor}",
    ]

    for pip in other_pips:
        pip.unlink()
        pip.symlink_to(pip_path)

    from .. import __main__

    pyodide_pythonpath = str(Path(__main__.__file__).parents[1])
    environment_vars = [f"PYTHONPATH={pyodide_pythonpath}"]
    import os

    for environment_var in ["VIRTUAL_ENV", "PATH", "PYODIDE_ROOT"]:
        value = os.environ.get(environment_var, "''")
        environment_vars.append(f"{environment_var}={value}")
    environment = " ".join(environment_vars)

    pyodide_path = bin / "pyodide"
    pyodide_path.write_text(
        dedent(
            f"""
            #!/bin/sh
            {environment} exec {sys.executable} -m pyodide_build.out_of_tree $@
            """
        )
    )
    pyodide_path.chmod(0o777)

    toload = ["micropip"]
    result = subprocess.run(
        [bin / "pip", "install", *toload],
        capture_output=True,
        encoding="utf8",
    )
    if result.returncode != 0:
        print("ERROR: failed to invoke pip")
        exit_with_stdio(result)

    result = subprocess.run(
        [
            bin / "python.js",
            "-c",
            dedent(
                """
            from pyodide import _package_loader;
            from _pyodide._importhook import UNVENDORED_STDLIBS_AND_TEST;
            _package_loader.TARGETS["lib"] = _package_loader.SITE_PACKAGES;
            from pyodide_js import loadPackage;
            loadPackage(UNVENDORED_STDLIBS_AND_TEST);
            """
            ),
        ],
        capture_output=True,
        encoding="utf8",
    )

    if result.returncode != 0:
        print("ERROR: failed to install unvendored stdlib modules")
        exit_with_stdio(result)

    print("Successfully created Pyodide virtual environment!")
