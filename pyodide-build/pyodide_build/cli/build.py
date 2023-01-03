import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
import typer  # type: ignore[import]
from unearth.evaluator import TargetPython
from unearth.finder import PackageFinder

from .. import common
from ..out_of_tree import build
from ..out_of_tree.utils import initialize_pyodide_root


def _fetch_pypi_package(package_spec, destdir):
    PYMAJOR = common.get_make_flag("PYMAJOR")
    PYMINOR = common.get_make_flag("PYMINOR")
    tp = TargetPython(
        py_ver=(int(PYMAJOR), int(PYMINOR)),
        platforms=[common.platform()],
        abis=[f"cp{PYMAJOR}{PYMINOR}"],
    )
    pf = PackageFinder(index_urls=["https://pypi.org/simple/"], target_python=tp)
    match = pf.find_best_match(package_spec)
    if match.best is None:
        if len(match.candidates) != 0:
            error = f"""Can't find version matching {package_spec}
versions found:
"""
            for c in match.candidates:
                error += "  " + str(c.version) + "\t"
            raise RuntimeError(error)
        else:
            raise RuntimeError(f"Can't find package: {package_spec}")
    with tempfile.TemporaryDirectory() as download_dir:
        return pf.download_and_unpack(
            link=match.best.link, location=destdir, download_dir=download_dir
        )


def pypi(
    package: str,
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,
) -> None:
    """Fetch a wheel from pypi, or build from source if none available."""
    initialize_pyodide_root()
    common.check_emscripten_version()
    backend_flags = ctx.args
    curdir = Path.cwd()
    (curdir / "dist").mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        temppath = Path(tmpdir)

        # get package from pypi
        package_path = _fetch_pypi_package(package, temppath)
        if not package_path.is_dir():
            # a pure-python wheel has been downloaded - just copy to dist folder
            shutil.copy(str(package_path), str(curdir / "dist"))
            print(f"Successfully fetched: {package_path.name}")
            return

        # sdist - needs building
        os.chdir(tmpdir)
        build.run(exports, backend_flags)
        for src in (temppath / "dist").iterdir():
            print(f"Built {str(src.name)}")
            shutil.copy(str(src), str(curdir / "dist"))


def url(
    package_url: str,
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,
) -> None:
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
            return
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
                print(os.listdir(tmpdir))
                build.run(exports, backend_flags)
                for src in (temppath / "dist").iterdir():
                    print(f"Built {str(src.name)}")
                    shutil.copy(str(src), str(curdir / "dist"))
            os.unlink(tf.name)


def source(
    source_location: "Optional[str]" = typer.Argument(None),
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,
) -> None:
    """Use pypa/build to build a Python package from source"""
    initialize_pyodide_root()
    common.check_emscripten_version()
    backend_flags = [source_location] + ctx.args
    build.run(exports, backend_flags)


# simple 'pyodide build' command
def main(
    source_location: "Optional[str]" = typer.Argument(
        "",
        help="Build source, can be source folder, pypi version specification, or url to a source dist archive or wheel file. If this is blank, it will build the current directory.",
    ),
    exports: str = typer.Option(
        "requested",
        help="Which symbols should be exported when linking .so files?",
    ),
    ctx: typer.Context = typer.Context,
) -> None:
    """Use pypa/build to build a Python package from source, pypi or url."""
    if not source_location:
        # build the current folder
        source(".", exports, ctx)
    elif source_location.find("://") != -1:
        url(source_location, exports, ctx)
    elif Path(source_location).is_dir():
        # a folder, build it
        source(source_location, exports, ctx)
    else:
        # try fetch from pypi
        pypi(source_location, exports, ctx)


main.typer_kwargs = {  # type: ignore[attr-defined]
    "context_settings": {
        "ignore_unknown_options": True,
        "allow_extra_args": True,
    },
}
