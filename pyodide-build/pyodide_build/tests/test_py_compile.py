import json
import sys
import textwrap
import traceback
import zipfile
from collections.abc import Mapping
from importlib.util import MAGIC_NUMBER
from pathlib import Path

import pytest

from pyodide_build._py_compile import (
    _get_py_compiled_archive_name,
    _py_compile_archive,
    _py_compile_archive_dir,
)


def _create_tmp_wheel(
    package_name: str,
    base_dir: Path,
    data: Mapping[str, str],
    version: str = "0.1.0",
    tag: str = "py3-none-any",
) -> Path:
    """Create a wheel with some test files

    The metadata is not correct, so it's mostly a zip with some files
    """
    wheel_path = base_dir / f"{package_name}-{version}-{tag}.whl"
    with zipfile.ZipFile(
        wheel_path, mode="w", compression=zipfile.ZIP_DEFLATED
    ) as fh_zip:
        for key, val in data.items():
            fh_zip.writestr(key, val)
    return wheel_path


def test_py_compile_archive(tmp_path):
    wheel_data = {
        "a.so": "abc",
        "b.txt": "123",
        "METADATA": "a",
        "packageA/a.py": "1+1",
        "packageB/c/d/e/f.py": "x = 1",
    }
    input_wheel_path = _create_tmp_wheel(
        "packagea", base_dir=tmp_path, data=wheel_data, tag="py3-none-any"
    )
    assert input_wheel_path.name == "packagea-0.1.0-py3-none-any.whl"
    output_wheel_path = _py_compile_archive(input_wheel_path)
    assert output_wheel_path is not None
    assert (
        output_wheel_path.name
        == f"packagea-0.1.0-cp3{sys.version_info[1]}-none-any.whl"
    )

    with zipfile.ZipFile(output_wheel_path) as fh_zip:
        # Files are the same except for .py -> .pyc conversion
        assert {el for el in fh_zip.namelist() if not el.endswith(".pyc")} == {
            el for el in wheel_data if not el.endswith(".py")
        }

        for key, val_expected in wheel_data.items():
            if not key.endswith(".py"):
                # Files other than .py are preserved
                val = fh_zip.read(key)
                assert val.decode("utf-8") == val_expected
            else:
                val = fh_zip.read(key + "c")
                # Looks like Python bytecode
                assert key.encode("utf-8") in val
                assert val.startswith(MAGIC_NUMBER)


@pytest.mark.parametrize("keep", [True, False])
def test_py_compile_zip(tmp_path, keep):
    archive_path = tmp_path / "test1.zip"
    with zipfile.ZipFile(archive_path, mode="w") as fh_zip:
        fh_zip.writestr("packageA/c/a.py", "1+1")
        fh_zip.writestr("packageA/d.c", "x = 1")
    out_path = _py_compile_archive(archive_path, keep=keep)
    assert out_path == archive_path

    if keep:
        expected = {"test1.zip", "test1.zip.old"}
    else:
        expected = {"test1.zip"}

    assert set(el.name for el in tmp_path.glob("*")) == expected

    with zipfile.ZipFile(archive_path) as fh_zip:
        assert fh_zip.namelist() == ["packageA/c/a.pyc", "packageA/d.c"]


def test_py_compile_zip_no_py(tmp_path):
    archive_path = tmp_path / "test1.zip"
    with zipfile.ZipFile(archive_path, mode="w") as fh_zip:
        fh_zip.writestr("packageA/d.c", "x = 1")
    out_path = _py_compile_archive(archive_path)
    assert out_path is None

    # File is not modified
    with zipfile.ZipFile(archive_path) as fh_zip:
        assert fh_zip.namelist() == ["packageA/d.c"]


def test_py_compile_exceptions(tmp_path):
    wheel_data = {
        "a.py": "x = 1",
        "b.py": textwrap.dedent(
            """
               def func1():
                   raise ValueError()

               def func2():
                   func1()
               """
        ),
    }
    input_wheel_path = _create_tmp_wheel(
        "packagea", base_dir=tmp_path, data=wheel_data, tag="py3-none-any"
    )
    output_wheel_path = _py_compile_archive(input_wheel_path)
    assert output_wheel_path is not None
    with zipfile.ZipFile(output_wheel_path) as fh_zip:
        (tmp_path / "_py_compile_test_a.pyc").write_bytes(fh_zip.read("a.pyc"))
        (tmp_path / "_py_compile_test_b.pyc").write_bytes(fh_zip.read("b.pyc"))

    sys.path.append(str(tmp_path))
    import _py_compile_test_a

    assert _py_compile_test_a.x == 1

    import _py_compile_test_b

    try:
        _py_compile_test_b.func2()
    except ValueError:
        tb = traceback.format_exc()
        assert tb.splitlines()[-3:] == [
            '  File "b.py", line 6, in func2',
            '  File "b.py", line 3, in func1',
            "ValueError",
        ]
    else:
        raise AssertionError()


def test_py_compile_not_wheel(tmp_path):
    input_path = tmp_path / "some_file.whl"
    input_path.write_bytes(b"")
    assert _py_compile_archive(input_path) is None


def test_get_py_compiled_archive_name(tmp_path):
    with zipfile.ZipFile(tmp_path / "test1.zip", mode="w") as fh_zip:
        fh_zip.writestr("packageA/c/a.py", "1+1")
        fh_zip.writestr("packageA/d.c", "x = 1")

    # Zip file contains .py files, so it should be py-compiled keeping the same name
    assert _get_py_compiled_archive_name(tmp_path / "test1.zip") == ("test1.zip")

    with zipfile.ZipFile(tmp_path / "test2.zip", mode="w") as fh_zip:
        fh_zip.writestr("packageA/a", "1+1")

    # No .py files in the zip file, it should not be py-compiled
    assert _get_py_compiled_archive_name(tmp_path / "test2.zip") is None

    # Other file formats than .zip and .whl should not be py-compiled
    (tmp_path / "test3.tar.gz").write_bytes(b"")

    assert _get_py_compiled_archive_name(tmp_path / "test3.tar.gz") is None


@pytest.mark.parametrize("with_lockfile", [True, False])
def test_py_compile_archive_dir(tmp_path, with_lockfile):
    archive_path = tmp_path / "test1.zip"
    with zipfile.ZipFile(archive_path, mode="w") as fh_zip:
        fh_zip.writestr("packageA/c/a.py", "1+1")
        fh_zip.writestr("packageA/d.c", "x = 1")

    wheel_data = {
        "a.so": "abc",
        "b.txt": "123",
        "METADATA": "a",
        "packageB/a.py": "1+1",
    }

    input_wheel_path = _create_tmp_wheel(
        "packageB", base_dir=tmp_path, data=wheel_data, tag="py3-none-any"
    )

    lockfile_path = tmp_path / "pyodide-lock.json"
    lockfile = {
        "info": {"arch": "wasm32"},
        "packages": {
            "packageA": {"version": "1.0", "file_name": archive_path.name},
            "packageB": {"version": "1.0", "file_name": input_wheel_path.name},
            "packageC": {
                "version": "1.0",
                "file_name": "some-path.tar",
                "checksum": "123",
            },
        },
    }

    expected_in = {"test1.zip", "packageB-0.1.0-py3-none-any.whl"}
    expected_out = {"test1.zip", "packageb-0.1.0-cp311-none-any.whl"}
    if with_lockfile:
        with open(lockfile_path, "w") as fh:
            json.dump(lockfile, fh)
        expected_in.add("pyodide-lock.json")
        expected_out.add("pyodide-lock.json")

    assert set(el.name for el in tmp_path.glob("*")) == expected_in

    mapping = _py_compile_archive_dir(tmp_path, keep=False)

    assert mapping == {
        "packageB-0.1.0-py3-none-any.whl": "packageb-0.1.0-cp311-none-any.whl",
        "test1.zip": "test1.zip",
    }

    assert set(el.name for el in tmp_path.glob("*")) == expected_out

    if not with_lockfile:
        return

    with open(lockfile_path) as fh:
        lockfile_new = json.load(fh)

    assert lockfile_new["info"] == lockfile["info"]
    assert lockfile_new["packages"]["packageA"]["file_name"] == "test1.zip"
    # sha256 is not reproducible, since it depends on the timestamp
    assert len(lockfile_new["packages"]["packageA"]["sha256"]) == 64

    assert (
        lockfile_new["packages"]["packageB"]["file_name"]
        == "packageb-0.1.0-cp311-none-any.whl"
    )
    assert len(lockfile_new["packages"]["packageA"]["sha256"]) == 64

    assert lockfile_new["packages"]["packageC"] == {
        "version": "1.0",
        "file_name": "some-path.tar",
        "checksum": "123",
    }
