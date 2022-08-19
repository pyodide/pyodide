import argparse
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

from ..common import get_pyodide_root


def main(parser_args: argparse.Namespace) -> None:
    run(Path(parser_args.dest))


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = "Create a Pyodide virtual environment"
    parser.add_argument("dest", help="directory to create virtualenv at", type=str)
    return parser


def run(dest: Path) -> None:
    from virtualenv import session_via_cli  # type: ignore[import]

    if dest.exists():
        print(f"dest directory '{dest}' already exists")
        sys.exit(1)

    interp_path = get_pyodide_root() / "tools/python.js"
    version_major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    session = session_via_cli(["--no-wheel", "-p", str(interp_path), str(dest)])
    pyodide_version = session.interpreter.version.partition(" ")[0].split(".")
    if sys.version_info.major != int(
        pyodide_version[0]
    ) or sys.version_info.minor != int(pyodide_version[1]):
        expected_version = ".".join(pyodide_version[:2])
        print(
            f"Expected host Python version to be {expected_version} but got version {version_major_minor}"
        )
        sys.exit(1)

    session.run()

    dest = Path(session.creator.dest).absolute()
    (dest / "pip.conf").write_text(
        dedent(
            """
            [install]
            only-binary=:all:
            find-links=/home/hood/Documents/programming/pyodide/dist/
            """
        ).strip()
    )

    bin = dest / "bin"

    host_python_path = bin / "python3.10-host"
    host_python_path.symlink_to(sys.executable)
    pip_path = bin / "pip"
    result = subprocess.run(
        [
            bin / "python",
            "-c",
            "import os, sys, sysconfig,  platform; print([os.name, sys.platform, sysconfig.get_platform()])",
        ],
        capture_output=True,
        encoding="utf8",
    )

    pip_path.write_text(
        dedent(
            f"""
            #!{host_python_path}
            # -*- coding: utf-8 -*-
            import os
            import sys

            posix = os
            os_name, sys_platform, host_platform = {result.stdout}
            os.name = os_name
            sys.platform = sys_platform
            os.environ["_PYTHON_HOST_PLATFORM"] = host_platform

            import re
            import sys
            from pip._internal.cli.main import main
            if __name__ == '__main__':
                sys.argv[0] = re.sub(r'(-script\\.pyw|\\.exe)?$', '', sys.argv[0])
                sys.exit(main())
            """
        ).strip()
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

    toload = ["ssl", "micropip"]
    subprocess.run(
        [
            bin / "python",
            "-c",
            f"from pyodide_js import loadPackage; loadPackage({toload!r})",
        ]
    )
