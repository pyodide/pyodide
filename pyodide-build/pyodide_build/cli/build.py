import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
import typer

from .. import common
from ..out_of_tree import build
from ..out_of_tree.pypi import (
    build_dependencies_for_wheel,
    build_wheels_from_pypi_requirements,
    fetch_pypi_package,
)
from ..out_of_tree.utils import initialize_pyodide_root


def pypi(
    package: str,
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,
) -> Path:
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
            dest_file = curdir / "dist" / package_path.name
            shutil.copyfile(str(package_path), curdir / "dist" / package_path.name)
            print(f"Successfully fetched: {package_path.name}")
            return dest_file

        # sdist - needs building
        os.chdir(tmpdir)
        built_wheel = build.run(exports, backend_flags, outdir=curdir / "dist")
        os.chdir(curdir)
        return built_wheel


def url(
    package_url: str,
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,
) -> Path:
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
            out_path = Path(f"dist/{filename}").resolve()
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
                    os.chdir(temppath)
                wheel_path = build.run(exports, backend_flags, outdir=curdir / "dist")
            os.unlink(tf.name)
            return wheel_path


def source(
    source_location: str,
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,
) -> Path:
    """Use pypa/build to build a Python package from source"""
    initialize_pyodide_root()
    orig_dir = Path.cwd()
    if source_location != ".":
        # build in this folder
        os.chdir(source_location)
    common.check_emscripten_version()
    backend_flags = ctx.args
    built_wheel = build.run(exports, backend_flags, outdir=orig_dir / "dist")
    os.chdir(orig_dir)
    return built_wheel


# simple 'pyodide build' command
def main(
    source_location: "Optional[str]" = typer.Argument(
        "",
        help="Build source, can be source folder, pypi version specification, or url to a source dist archive or wheel file. If this is blank, it will build the current directory.",
    ),
    requirements_txt: str = typer.Option(
        "",
        "--requirements",
        "-r",
        help="Build a list of package requirements from a requirements.txt file",
    ),
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    build_dependencies: bool = typer.Option(
        False, help="Fetch non-pyodide dependencies from pypi and build them too."
    ),
    output_lockfile: str = typer.Option(
        "",
        help="Output list of resolved dependencies to a file in requirements.txt format",
    ),
    skip_dependency: list[str] = typer.Option(
        [],
        help="Skip building or resolving a single dependency. Use multiple times or provide a comma separated list to skip multiple dependencies.",
    ),
    compression_level: int = typer.Option(
        6, help="Compression level to use for the created zip file"
    ),
    ctx: typer.Context = typer.Context,
) -> None:
    """Use pypa/build to build a Python package from source, pypi or url."""
    extras: list[str] = []

    if len(requirements_txt) > 0:
        # a requirements.txt - build it (and optionally deps)
        if not Path(requirements_txt).exists():
            raise RuntimeError(
                f"Couldn't find requirements text file {requirements_txt}"
            )
        reqs = []
        with open(requirements_txt) as f:
            raw_reqs = [x.strip() for x in f.readlines()]
        for x in raw_reqs:
            # remove comments
            comment_pos = x.find("#")
            if comment_pos != -1:
                x = x[:comment_pos].strip()
            if len(x) > 0:
                if x[0] == "-":
                    raise RuntimeError(
                        f"pyodide build only supports name-based PEP508 requirements. [{x}] will not work."
                    )
                if x.find("@") != -1:
                    raise RuntimeError(
                        f"pyodide build does not support URL based requirements. [{x}] will not work"
                    )
                reqs.append(x)
        try:
            build_wheels_from_pypi_requirements(
                reqs,
                Path("./dist").resolve(),
                build_dependencies,
                skip_dependency,
                exports,
                ctx.args,
                output_lockfile=output_lockfile,
            )
        except BaseException as e:
            import traceback

            print("Failed building multiple wheels:", traceback.format_exc())
            raise e
        return

    if source_location is not None:
        extras = re.findall(r"\[(\w+)\]", source_location)
        if len(extras) != 0:
            source_location = source_location[0 : source_location.find("[")]
    if not source_location:
        # build the current folder
        wheel = source(".", exports, ctx)
    elif source_location.find("://") != -1:
        wheel = url(source_location, exports, ctx)
    elif Path(source_location).is_dir():
        # a folder, build it
        wheel = source(source_location, exports, ctx)
    elif source_location.find("/") == -1:
        # try fetch or build from pypi
        wheel = pypi(source_location, exports, ctx)
    else:
        raise RuntimeError(f"Couldn't determine source type for {source_location}")
    # now build deps for wheel
    if build_dependencies:
        try:
            build_dependencies_for_wheel(
                wheel,
                extras,
                skip_dependency,
                exports,
                ctx.args,
                output_lockfile=output_lockfile,
                compression_level=compression_level,
            )
        except BaseException as e:
            import traceback

            print("Failed building dependencies for wheel:", traceback.format_exc())
            wheel.unlink()
            raise e


main.typer_kwargs = {  # type: ignore[attr-defined]
    "context_settings": {
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
}
