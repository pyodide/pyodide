import argparse
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
import typer  # type: ignore[import]

from .. import buildall, common
from ..out_of_tree import build
from ..out_of_tree.pypi import build_dependencies_for_wheel, fetch_pypi_package
from ..out_of_tree.utils import initialize_pyodide_root

app = typer.Typer()


def pypi(
    package: str,
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,
) -> str:
    """Fetch a wheel from pypi, or build from source if none available."""
    initialize_pyodide_root()
    common.check_emscripten_version()
    backend_flags = ctx.args
    curdir = Path.cwd()
    (curdir / "dist").mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        temppath = Path(tmpdir)

        # get package from pypi
        package_path = fetch_pypi_package(package, temppath)
        if not package_path.is_dir():
            # a pure-python wheel has been downloaded - just copy to dist folder
            shutil.copy(str(package_path), str(curdir / "dist"))
            print(f"Successfully fetched: {package_path.name}")
            return str(package_path)

        # sdist - needs building
        os.chdir(tmpdir)
        built_wheel = Path(build.run(exports, backend_flags))
        wheel_name = str(curdir / "dist" / built_wheel)
        shutil.copyfile(str(built_wheel), str(wheel_name))
        return wheel_name


def url(
    package_url: str,
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,
) -> str:
    """Fetch a wheel or build sdist from url."""
    initialize_pyodide_root()
    common.check_emscripten_version()
    backend_flags = ctx.args
    curdir = Path.cwd()
    (curdir / "dist").mkdir(exist_ok=True)
    with requests.get(package_url, stream=True) as response:
        parsed_url = urlparse(response.url)
        filename = os.path.basename(parsed_url.path)
        name_base, ext = os.path.splitext(filename)
        if ext == ".gz" and name_base.rfind(".") != -1:
            ext = name_base[name_base.rfind(".") :] + ext
        if ext.lower() == ".whl":
            # just copy wheel into dist and return
            out_path = f"dist/{filename}"
            with open(out_path, "b") as f:
                for chunk in response.iter_content(chunk_size=1048576):
                    f.write(chunk)
            return out_path
        else:
            tf = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            for chunk in response.iter_content(chunk_size=1048576):
                tf.write(chunk)
            tf.close()
            with tempfile.TemporaryDirectory() as tmpdir:
                temppath = Path(tmpdir)
                shutil.unpack_archive(tf.name, tmpdir)
                folder_list = list(temppath.iterdir())
                if len(folder_list) == 1 and folder_list[0].is_dir():
                    # unzipped into subfolder
                    os.chdir(folder_list[0])
                else:
                    # unzipped here
                    os.chdir(tmpdir)
                built_wheel = Path(build.run(exports, backend_flags))
                wheel_name = str(curdir / "dist" / built_wheel)
                shutil.copyfile(str(built_wheel), str(wheel_name))
            os.unlink(tf.name)
            return wheel_name


def source(
    source_location: str,
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,
) -> str:
    """Use pypa/build to build a Python package from source"""
    initialize_pyodide_root()
    orig_dir = Path.cwd()
    if source_location != ".":
        # build in this folder
        os.chdir(source_location)
    common.check_emscripten_version()
    backend_flags = ctx.args
    built_wheel = Path(build.run(exports, backend_flags, outdir=orig_dir / "dist"))
    os.chdir(orig_dir)
    return str(built_wheel)


@app.command()  # type: ignore[misc]
def recipe(
    packages: list[str] = typer.Argument(
        ..., help="Packages to build, or * for all packages in recipe directory"
    ),
    output: str = typer.Option(
        None,
        help="Path to output built packages and repodata.json. "
        "If not specified, the default is `PYODIDE_ROOT/dist`.",
    ),
    cflags: str = typer.Option(
        None, help="Extra compiling flags. Default: SIDE_MODULE_CFLAGS"
    ),
    cxxflags: str = typer.Option(
        None, help="Extra compiling flags. Default: SIDE_MODULE_CXXFLAGS"
    ),
    ldflags: str = typer.Option(
        None, help="Extra linking flags. Default: SIDE_MODULE_LDFLAGS"
    ),
    target_install_dir: str = typer.Option(
        None,
        help="The path to the target Python installation. Default: TARGETINSTALLDIR",
    ),
    host_install_dir: str = typer.Option(
        None,
        help="Directory for installing built host packages. Default: HOSTINSTALLDIR",
    ),
    log_dir: str = typer.Option(None, help="Directory to place log files"),
    force_rebuild: bool = typer.Option(
        False,
        help="Force rebuild of all packages regardless of whether they appear to have been updated",
    ),
    n_jobs: int = typer.Option(4, help="Number of packages to build in parallel"),
    root: str = typer.Option(
        None, help="The root directory of the Pyodide.", envvar="PYODIDE_ROOT"
    ),
    recipe_dir: str = typer.Option(
        None,
        help="The directory containing the recipe of packages. "
        "If not specified, the default is `packages` in the root directory.",
    ),
    ctx: typer.Context = typer.Context,
) -> None:
    """Build packages using yaml recipes and create repodata.json"""
    pyodide_root = common.search_pyodide_root(Path.cwd()) if not root else Path(root)
    recipe_dir_ = pyodide_root / "packages" if not recipe_dir else Path(recipe_dir)
    output_dir = pyodide_root / "dist" if not output else Path(output)

    # Note: to make minimal changes to the existing pyodide-build entrypoint,
    #       keep arguments of buildall unghanged.
    # TODO: refactor this when we remove pyodide-build entrypoint.
    args = argparse.Namespace(**ctx.params)
    args.dir = args.recipe_dir

    if len(args.packages) == 1 and "," in args.packages[0]:
        # Handle packages passed with old comma separated syntax.
        # This is to support `PYODIDE_PACKAGES="pkg1,pkg2,..." make` syntax.
        args.only = args.packages[0].replace(" ", "")
    else:
        args.only = ",".join(args.packages)

    args = buildall.set_default_args(args)

    buildall.build_packages(recipe_dir_, output_dir, args)


# simple 'pyodide build' command
@app.command()  # type: ignore[misc]
def main(
    source_location: "Optional[str]" = typer.Argument(
        "",
        help="Build source, can be source folder, pypi version specification, or url to a source dist archive or wheel file. If this is blank, it will build the current directory.",
    ),
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    build_dependencies: bool = typer.Option(
        False, help="Fetch non-pyodide dependencies from pypi and build them too."
    ),
    skip_dependency: list[str] = typer.Option(
        [],
        help="Skip building or resolving a single dependency. Use multiple times to skip multiple dependencies.",
    ),
    ctx: typer.Context = typer.Context,
) -> None:
    """Use pypa/build to build a Python package from source, pypi or url."""
    if not source_location:
        # build the current folder
        wheel = source(".", exports, ctx)
    elif source_location.find("://") != -1:
        wheel = url(source_location, exports, ctx)
    elif Path(source_location).is_dir():
        # a folder, build it
        wheel = source(source_location, exports, ctx)
    else:
        # try fetch from pypi
        wheel = pypi(source_location, exports, ctx)
    # now build deps for wheel
    if build_dependencies:
        build_dependencies_for_wheel(
            Path(wheel), [], skip_dependency, exports, ctx.args
        )


main.typer_kwargs = {
    "context_settings": {
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
}
