def out_of_tree_main():
    import os
    from pathlib import Path

    env = Path(".pyodide-xbuildenv")
    os.environ["PYODIDE_ROOT"] = str(env / "xbuildenv/pyodide-root")
    if not env.exists():
        from .install_xbuildenv import download_xbuild_env, install_xbuild_env
        download_xbuild_env(env)
        install_xbuild_env(env)

    from .wrapper import run
    import sys
    run(sys.argv[1:])

