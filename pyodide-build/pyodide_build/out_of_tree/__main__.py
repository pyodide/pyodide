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


def main():
    main_parser = argparse.ArgumentParser(prog="pywasmbuild")
    main_parser.description = "Tools for creating Python extension modules for the wasm32-unknown-emscripten platform"
    subparsers = main_parser.add_subparsers(help="action")
    for module in [build]:
        modname = module.__name__.rpartition(".")[-1]
        parser = module.make_parser(subparsers.add_parser(modname))
        parser.set_defaults(func=module.main)

    env = Path(".pyodide-xbuildenv")
    os.environ["PYODIDE_ROOT"] = str(env / "xbuildenv/pyodide-root")
    ensure_env_installed(env)

    args = main_parser.parse_args()
    if hasattr(args, "func"):
        # run the selected action
        args.func(args)
    else:
        main_parser.print_help()
