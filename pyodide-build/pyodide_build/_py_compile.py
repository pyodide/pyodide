import py_compile
import shutil
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from packaging.tags import Tag
from packaging.utils import parse_wheel_filename

from .logger import logger, set_log_level


def _specialize_convert_tags(tags: set[Tag] | frozenset[Tag], wheel_name: str) -> Tag:
    """Convert a sequence of wheel tags to a single tag corresponding
    to the current interpreter and compatible with the py -> pyc compilation.

    Having more than one output tag is not supported.

    Examples
    --------
    >>> from packaging.tags import parse_tag
    >>> tags = parse_tag("py2.py3-none-any")
    >>> str(_specialize_convert_tags(set(tags), ""))
    'cp310-none-any'
    >>> tags = parse_tag("cp310-cp310-emscripten_3_1_24_wasm32")
    >>> str(_specialize_convert_tags(set(tags), ""))
    'cp310-cp310-emscripten_3_1_24_wasm32'
    >>> tags = parse_tag("py310.py311-any-none")
    >>> str(_specialize_convert_tags(set(tags), ""))
    'cp310-any-none'
    >>> tags = parse_tag("py36-abi3-none")
    >>> str(_specialize_convert_tags(set(tags), ""))
    'cp310-abi3-none'
    """
    if len(tags) == 0:
        raise ValueError("Failed to parse tags from the wheel file name: {wheel_name}!")

    output_tags = set()
    interpreter = "cp" + "".join(str(el) for el in sys.version_info[:2])
    for tag in tags:
        output_tags.add(
            Tag(interpreter=interpreter, abi=tag.abi, platform=tag.platform)
        )

    if len(output_tags) > 1:
        # See https://github.com/pypa/packaging/issues/616
        raise NotImplementedError(
            "Found more than one output tag after py-compilation: "
            f"{[str(tag) for tag in output_tags]} in {wheel_name}"
        )

    return list(output_tags)[0]


def _py_compile_wheel_name(wheel_name: str) -> str:
    """Return the name of the py-compiled wheel

    See https://peps.python.org/pep-0427/ for more information.

    Examples
    --------
    >>> _py_compile_wheel_name('micropip-0.1.0-py3-none-any.whl')
    'micropip-0.1.0-cp310-none-any.whl'
    >>> _py_compile_wheel_name("numpy-1.22.4-cp310-cp310-emscripten_3_1_24_wasm32.whl")
    'numpy-1.22.4-cp310-cp310-emscripten_3_1_24_wasm32.whl'
    >>> # names with '_' are preserved (instead of using '-')
    >>> _py_compile_wheel_name("a_b-0.0.0-cp310-cp310-emscripten_3_1_24_wasm32.whl")
    'a_b-0.0.0-cp310-cp310-emscripten_3_1_24_wasm32.whl'
    >>> # if there are multiple tags (e.g. py2 & py3), we only keep the relevant one
    >>> _py_compile_wheel_name('attrs-21.4.0-py2.py3-none-any.whl')
    'attrs-21.4.0-cp310-none-any.whl'


    # >>> msg = "Processing more than one tag is not implemented"
    # >>> with pytest.rases(NotImplementedError, match=msg):
    # ...     _py_compile_wheel_name("numpy-1.23.4-cp310-cp310-manylinux_2_17_aarch64.manylinux2014_aarch64.whl")
    """
    name, version, build, tags = parse_wheel_filename(wheel_name)
    if build:
        # TODO: not sure what to do here, but we never have such files in Pyodide
        # Opened https://github.com/pypa/packaging/issues/616 about it.
        raise NotImplementedError(f"build tag {build} not implemented")
    output_name = f"{name.replace('-', '_')}-{version}-"
    output_name += str(_specialize_convert_tags(tags, wheel_name=wheel_name))
    return output_name + ".whl"


def _compile(
    input_path: Path, output_path: Path, keep: bool = True, verbose: bool = True
) -> None:
    """Compile all .py files in the zip archive to .pyc files.

    Parameters
    ----------
    input_path
        Path to the input archive.
    output_path
        Path to the output archive.
    """
    output_name = output_path.name

    with set_log_level(logger, verbose):
        logger.debug(f"Running py-compile on {input_path} to {output_path}")

        with zipfile.ZipFile(
            input_path
        ) as fh_zip_in, TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            output_path_tmp = temp_dir / output_name
            with zipfile.ZipFile(
                output_path_tmp, mode="w", compression=zipfile.ZIP_DEFLATED
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
                        str(tmp_path_py),
                        cfile=str(tmp_path_pyc),
                        dfile=name,
                        doraise=True,
                    )

                    fh_zip_out.writestr(name + "c", tmp_path_pyc.read_bytes())
            if output_path == input_path:
                if keep:
                    logger.debug("Adding .old suffix to avoid overwriting input file.")

                    backup_path = input_path.with_suffix(input_path.suffix + ".old")
                    input_path.rename(backup_path)
            elif not keep:
                # Remove input file
                input_path.unlink()

            shutil.copyfile(output_path_tmp, output_path)


def _py_compile_wheel(
    wheel_path: Path,
    keep: bool = True,
    verbose: bool = True,
) -> Path:
    """Compile .py files to .pyc in a wheel

    All non Python files are kept unchanged.

    Parameters
    ----------
    wheel_path
        input wheel path
    keep
        if False, delete the input file. Otherwise, it will be either kept or
        renamed with a suffix .whl.old (if the input path == computed output
        path)
    verbose
        print logging information

    Returns
    -------
    wheel_path_out
        processed wheel with .pyc files.


    """
    if wheel_path.suffix != ".whl":
        raise ValueError(f"Error: only .whl files are supported, got {wheel_path.name}")

    if not wheel_path.exists():
        raise FileNotFoundError(f"{wheel_path} does not exist!")

    wheel_name_out = _py_compile_wheel_name(wheel_path.name)
    wheel_path_out = wheel_path.parent / wheel_name_out

    _compile(wheel_path, wheel_path_out, keep=keep, verbose=verbose)

    return wheel_path_out
