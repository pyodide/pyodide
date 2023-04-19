import itertools
import json
import py_compile
import shutil
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from packaging.tags import Tag
from packaging.utils import parse_wheel_filename

from pyodide_build.common import _get_sha256_checksum

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
    'cp311-none-any'
    >>> tags = parse_tag("cp311-cp311-emscripten_3_1_24_wasm32")
    >>> str(_specialize_convert_tags(set(tags), ""))
    'cp311-cp311-emscripten_3_1_24_wasm32'
    >>> tags = parse_tag("py310.py311-any-none")
    >>> str(_specialize_convert_tags(set(tags), ""))
    'cp311-any-none'
    >>> tags = parse_tag("py36-abi3-none")
    >>> str(_specialize_convert_tags(set(tags), ""))
    'cp311-abi3-none'
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
    'micropip-0.1.0-cp311-none-any.whl'
    >>> _py_compile_wheel_name("numpy-1.22.4-cp311-cp311-emscripten_3_1_24_wasm32.whl")
    'numpy-1.22.4-cp311-cp311-emscripten_3_1_24_wasm32.whl'
    >>> # names with '_' are preserved (instead of using '-')
    >>> _py_compile_wheel_name("a_b-0.0.0-cp311-cp311-emscripten_3_1_24_wasm32.whl")
    'a_b-0.0.0-cp311-cp311-emscripten_3_1_24_wasm32.whl'
    >>> # if there are multiple tags (e.g. py2 & py3), we only keep the relevant one
    >>> _py_compile_wheel_name('attrs-21.4.0-py2.py3-none-any.whl')
    'attrs-21.4.0-cp311-none-any.whl'


    # >>> msg = "Processing more than one tag is not implemented"
    # >>> with pytest.rases(NotImplementedError, match=msg):
    # ...     _py_compile_wheel_name("numpy-1.23.4-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl")
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
    input_path: Path,
    output_path: Path,
    keep: bool = True,
    verbose: bool = True,
    compression_level: int = 6,
) -> None:
    """Compile all .py files in the zip archive to .pyc files.

    Parameters
    ----------
    input_path
        Path to the input archive.
    output_path
        Path to the output archive.
    compression_level
        Level of zip compression to apply. 0 means no compression. If a strictly
        positive integer is provided, ZIP_DEFLATED option is used.
    """
    output_name = output_path.name

    with set_log_level(logger, verbose):
        logger.debug(f"Running py-compile on {input_path} to {output_path}")

        if compression_level > 0:
            compression = zipfile.ZIP_DEFLATED
        else:
            compression = zipfile.ZIP_STORED

        with zipfile.ZipFile(
            input_path
        ) as fh_zip_in, TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            output_path_tmp = temp_dir / output_name
            with zipfile.ZipFile(
                output_path_tmp,
                mode="w",
                compression=compression,
                compresslevel=compression_level,
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


def _py_compile_archive(
    input_path: Path,
    keep: bool = True,
    verbose: bool = True,
    compression_level: int = 6,
) -> Path | None:
    """Compile .py files to .pyc in a wheel or zip file.

    All non Python files are kept unchanged.

    Parameters
    ----------
    input_path
        input path to a .whl or .zip file
    keep
        if False, delete the input file. Otherwise, it will be either kept or
        renamed with a suffix .whl.old (if the input path == computed output
        path)
    verbose
        print logging information
    compression_level
        Level of zip compression to apply. 0 means no compression. If a strictly
        positive integer is provided, ZIP_DEFLATED option is used.

    Returns
    -------
    path
        path to processed archive with .pyc files. Or None if the file was not py-compiled
        (e.g. if it's a zip with no .py files)
    """
    if input_path.suffix not in [".whl", ".zip"]:
        raise ValueError(
            f"Error: only .whl or .zip files are supported, got {input_path.name}"
        )

    if not input_path.exists():
        raise FileNotFoundError(f"{input_path} does not exist!")

    name_out = _get_py_compiled_archive_name(input_path)
    if name_out is None:
        return None
    path_out = input_path.parent / name_out

    _compile(
        input_path,
        path_out,
        keep=keep,
        verbose=verbose,
        compression_level=compression_level,
    )

    return path_out


def _get_py_compiled_archive_name(path: Path) -> str | None:
    """Return the name of the py-compiled wheel or zip file

    Returns None if the file should not be py-compiled.

    Examples
    --------
    >>> _get_py_compiled_archive_name(Path("snowballstemmer-2.2.0-py2.py3-none-any.whl"))
    'snowballstemmer-2.2.0-cp311-none-any.whl'
    >>> _get_py_compiled_archive_name(Path("test-1.0.0.zip"))
    """
    # TODO: fix py-compilation of the following packages
    if path.name.startswith(("RobotRaconteur", "astropy-", "opencv_python-")):
        return None

    if path.suffix == ".whl":
        try:
            output_name = _py_compile_wheel_name(path.name)
            return output_name
        except Exception as e:
            print(e)
            return None
    elif path.name == "test-1.0.0.zip":
        # We don't want to py-compile the test package
        return None
    elif path.suffix == ".zip":
        # If it's a zip file with .py files, keep the same name
        with zipfile.ZipFile(path, "r") as zip_ref:
            if any(file.endswith(".py") for file in zip_ref.namelist()):
                return path.name
        return None
    else:
        return None


def _update_repodata(
    input_dir: Path, repodata: dict[str, Any], name_mapping: dict[str, str]
) -> dict[str, Any]:
    """Update repodata.json with the new names of the py-compiled wheels.

    Also update the checksums of the updated wheels
    """
    for row in repodata["packages"].values():
        if row.get("file_name") in name_mapping:
            row["file_name"] = name_mapping[row["file_name"]]
            row["sha256"] = _get_sha256_checksum(input_dir / row["file_name"])
    return repodata


def _py_compile_archive_dir(
    input_dir: Path,
    keep: bool = True,
    verbose: bool = True,
    compression_level: int = 6,
) -> dict[str, str]:
    """Py-compile all wheels or zip files in a directory.

    All .py files in the wheels or zip files  are compiled to .pyc files. All
    non Python files are kept unchanged.
    For wheel the file names will be changed to include the Python version used
    for the compilation following the PEP 425 convention.


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
    compression_level
        Level of zip compression to apply. 0 means no compression. If a strictly
        positive integer is provided, ZIP_DEFLATED option is used.

    Returns
    -------
    name_mapping
        mapping between old and new file names
    """

    name_mapping = {}

    for file_path in itertools.chain(
        *[input_dir.glob(ext) for ext in ["*.zip", "*.whl"]]
    ):
        if (output_name := _get_py_compiled_archive_name(file_path)) is not None:
            _compile(
                file_path,
                file_path.parent / output_name,
                keep=keep,
                verbose=verbose,
                compression_level=compression_level,
            )
            name_mapping[file_path.name] = output_name

    repodata_path = input_dir / "repodata.json"
    if name_mapping and repodata_path.exists():
        if verbose:
            print(f"Updating {repodata_path.name}")
        with open(repodata_path) as fh:
            repodata = json.load(fh)
        repodata = _update_repodata(input_dir, repodata, name_mapping)
        with open(repodata_path, "w") as fh:
            json.dump(repodata, fh)
    return name_mapping
