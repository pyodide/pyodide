import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
import typer

from ..build_env import check_emscripten_version, init_environment
from ..out_of_tree import build
from ..out_of_tree.pypi import (
    build_dependencies_for_wheel,
    build_wheels_from_pypi_requirements,
    fetch_pypi_package,
)


def pypi(
    package: str,
    output_directory: Path,
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,  # type: ignore[assignment]
) -> Path:
    """Fetch a wheel from pypi, or build from source if none available."""
    backend_flags = ctx.args
    with tempfile.TemporaryDirectory() as tmpdir:
        srcdir = Path(tmpdir)

        # get package from pypi
        package_path = fetch_pypi_package(package, srcdir)
        if not package_path.is_dir():
            # a pure-python wheel has been downloaded - just copy to dist folder
            dest_file = output_directory / package_path.name
            shutil.copyfile(str(package_path), output_directory / package_path.name)
            print(f"Successfully fetched: {package_path.name}")
            return dest_file

        built_wheel = build.run(srcdir, output_directory, exports, backend_flags)
        return built_wheel


def download_url(url: str, output_directory: Path) -> str:
    with requests.get(url, stream=True) as response:
        urlpath = Path(urlparse(response.url).path)
        if urlpath.suffix == ".gz":
            urlpath = urlpath.with_suffix("")
        file_name = urlpath.name
        with open(output_directory / file_name, "wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        return file_name


def url(
    package_url: str,
    output_directory: Path,
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,  # type: ignore[assignment]
) -> Path:
    """Fetch a wheel or build sdist from url."""
    backend_flags = ctx.args
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        filename = download_url(package_url, tmppath)
        if Path(filename).suffix == ".whl":
            shutil.move(tmppath / filename, output_directory / filename)
            return output_directory / filename

        builddir = tmppath / "build"
        shutil.unpack_archive(tmppath / filename, builddir)
        files = list(builddir.iterdir())
        if len(files) == 1 and files[0].is_dir():
            # unzipped into subfolder
            builddir = files[0]
        wheel_path = build.run(builddir, output_directory, exports, backend_flags)
        return wheel_path


def source(
    source_location: Path,
    output_directory: Path,
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,  # type: ignore[assignment]
) -> Path:
    """Use pypa/build to build a Python package from source"""
    backend_flags = ctx.args
    built_wheel = build.run(source_location, output_directory, exports, backend_flags)
    return built_wheel


# simple 'pyodide build' command
def main(
    source_location: "Optional[str]" = typer.Argument(
        "",
        help="Build source, can be source folder, pypi version specification, or url to a source dist archive or wheel file. If this is blank, it will build the current directory.",
    ),
    output_directory: str = typer.Option(
        "",
        "--outdir",
        "-o",
        help="which directory should the output be placed into?",
    ),
    output_directory_compat: str = typer.Option("", "--output-directory", hidden=True),
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
    ctx: typer.Context = typer.Context,  # type: ignore[assignment]
) -> None:
    """Use pypa/build to build a Python package from source, pypi or url."""

    init_environment()
    check_emscripten_version()

    if output_directory_compat:
        print(
            "--output-directory is deprecated, use --outdir or -o instead",
            file=sys.stderr,
        )
    if output_directory_compat and output_directory:
        print("Cannot provide both --outdir and --output-directory", file=sys.stderr)
        sys.exit(1)
    output_directory = output_directory_compat or output_directory or "./dist"

    outpath = Path(output_directory).resolve()
    outpath.mkdir(exist_ok=True)
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
                outpath,
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
        wheel = source(Path.cwd(), outpath, exports, ctx)
    elif source_location.find("://") != -1:
        wheel = url(source_location, outpath, exports, ctx)
    elif Path(source_location).is_dir():
        # a folder, build it
        wheel = source(Path(source_location).resolve(), outpath, exports, ctx)
    elif source_location.find("/") == -1:
        # try fetch or build from pypi
        wheel = pypi(source_location, outpath, exports, ctx)
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
