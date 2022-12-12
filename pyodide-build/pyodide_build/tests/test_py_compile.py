import sys
import zipfile
from collections.abc import Mapping
from pathlib import Path

import pytest
from packaging.utils import InvalidWheelFilename

from pyodide_build._py_compile import _py_compile_wheel


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


def test_py_compile_wheel(tmp_path):
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
    output_wheel_path = _py_compile_wheel(input_wheel_path)
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
                assert key.encode("utf-8") + b"\xda\x08<module>" in val


def test_py_compile_not_wheel(tmp_path):
    input_path = tmp_path / "some_file.whl"
    input_path.write_bytes(b"")
    with pytest.raises(InvalidWheelFilename):
        _py_compile_wheel(input_path)
