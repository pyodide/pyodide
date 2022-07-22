import argparse
import os
from pathlib import Path

from . import build


def ensure_env_installed(env: Path) -> None:
    if env.exists():
        return
    from .. import __version__
    from ..install_xbuildenv import download_xbuild_env, install_xbuild_env

    download_xbuild_env(__version__, env)
    install_xbuild_env(env)


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = "Tools for creating Python extension modules for the wasm32-unknown-emscripten platform"

    subparsers = parser.add_subparsers(help="action")
    for module in [build]:
        modname = module.__name__.rpartition(".")[-1]
        subparser = module.make_parser(subparsers.add_parser(modname))
        subparser.set_defaults(subfunc=module.main)

    return parser


def main(args: argparse.Namespace) -> None:
    env = Path(".pyodide-xbuildenv")
    os.environ["PYODIDE_ROOT"] = str(env / "xbuildenv/pyodide-root")
    ensure_env_installed(env)

    if hasattr(args, "subfunc"):
        # run the selected action
        args.subfunc(args)
    else:
        raise RuntimeError("No subcommand selected")
