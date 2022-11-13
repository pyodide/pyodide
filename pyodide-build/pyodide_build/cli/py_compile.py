import py_compile
import shutil
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import typer  # type: ignore[import]
from packaging.tags import Tag
from packaging.utils import parse_wheel_filename


def _update_tag(tag: Tag) -> Tag:
    """Update the wheel tag for the py-compiled wheel"""
    interpreter = "cp" + "".join(str(el) for el in sys.version_info[:2])
    platform = tag.platform
    valid_interpreter = [f"py{sys.version_info[0]}", interpreter]
    if tag.interpreter not in valid_interpreter:
        raise ValueError(
            f"Unsupported interpreter {tag.interpreter}, must be one of {valid_interpreter}"
        )
    abi = interpreter
    valid_abi = ["none", abi]
    if tag.abi not in valid_abi:
        raise ValueError(
            f"Unsupported input wheel ABI: {tag.abi}, must be one of {valid_abi}"
        )
    return Tag(interpreter=interpreter, abi=abi, platform=platform)


def _py_compile_wheel_name(wheel_name: str) -> str:
    """Return the name of the py-compiled wheel

    See https://peps.python.org/pep-0427/ for more information.

    Examples
    --------
    >>> _py_compile_wheel_name('micropip-0.1.0-py3-none-any.whl')
    'micropip-0.1.0-cp310-cp310-any.whl'
    >>> _py_compile_wheel_name("numpy-1.22.4-cp310-cp310-emscripten_3_1_24_wasm32.whl")
    'numpy-1.22.4-cp310-cp310-emscripten_3_1_24_wasm32.whl'

    # >>> msg = "Processing more than one tag is not implemented"
    # >>> with pytest.rases(NotImplementedError, match=msg):
    # ...     _py_compile_wheel_name("numpy-1.23.4-cp310-cp310-manylinux_2_17_aarch64.manylinux2014_aarch64.whl")
    """
    name, version, build, tags = parse_wheel_filename(wheel_name)
    if len(tags) > 1:
        raise NotImplementedError(
            "Processing more than one tag is not implemented, "
            f"got {[str(tag) for tag in tags]}"
        )
    output_name = f"{name}-{version}-"
    if build:
        # TODO: not sure what to do here, but we never have such files in Pyodide
        raise NotImplementedError("build tag {build} not implemented")

    output_name += "_".join(str(_update_tag(tag)) for tag in tags)
    return output_name + ".whl"


def main(
    wheel_path: Path = typer.Argument(..., help="Path to the input wheel"),
) -> None:
    """Compile .py files to .pyc in a wheel"""
    if wheel_path.suffix != ".whl":
        typer.echo(f"Error: only .whl files are supported, got {wheel_path.name}")
        sys.exit(1)

    if not wheel_path.exists():
        raise FileNotFoundError(f"{wheel_path} does not exist!")

    wheel_name_out = _py_compile_wheel_name(wheel_path.name)
    wheel_path_out = wheel_path.parent / wheel_name_out
    typer.echo(f" - Processing input wheel {wheel_path}")

    with zipfile.ZipFile(wheel_path) as fh_zip_in, TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        wheel_path_tmp = temp_dir / wheel_name_out
        with zipfile.ZipFile(
            wheel_path_tmp, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as fh_zip_out:
            for name in fh_zip_in.namelist():
                if name.endswith(".pyc"):
                    # We are going to re-compile all .pyc files
                    continue

                stream = fh_zip_in.read(name)
                if not name.endswith(".py"):
                    # Write file without changes
                    fh_zip_out.writestr(name, stream)
                    continue

                # Otherwise write file to disk and run py_compile
                # Unfortunately py_compile doesn't support bytes input/output, it has to be real files
                tmp_path_py = temp_dir / name.replace("/", "_")
                tmp_path_py.write_bytes(stream)

                tmp_path_pyc = temp_dir / (tmp_path_py.name + "c")
                py_compile.compile(
                    str(tmp_path_py), cfile=str(tmp_path_pyc), doraise=True
                )

                fh_zip_out.writestr(name + "c", tmp_path_pyc.read_bytes())
        if wheel_name_out == wheel_path.name:
            typer.echo(
                f" - Renaming {wheel_path} to {wheel_path.name}.old to avoid overwriting input file"
            )
            wheel_path.rename(wheel_path.with_suffix(".whl.old"))

        shutil.copyfile(wheel_path_tmp, wheel_path_out)
        typer.echo(
            f" - Done running py_compile on the input wheel, output in {wheel_path_out}"
        )
