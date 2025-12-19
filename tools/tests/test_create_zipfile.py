import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parents[1]))
from create_zipfile import create_zipfile, default_filterfunc


@pytest.fixture(scope="module")
def temp_python_lib(tmp_path_factory):
    libdir = tmp_path_factory.mktemp("python")

    path = Path(libdir)

    (path / "test").mkdir()
    (path / "test" / "test_blah.py").touch()
    (path / "turtle.py").touch()

    (path / "module1.py").touch()
    (path / "module2.py").touch()

    (path / "hello_pyodide.py").write_text("def hello(): return 'hello'")

    yield libdir

@pytest.fixture(scope="module")
def temp_python_lib2(tmp_path_factory):
    libdir = tmp_path_factory.mktemp("python")

    path = Path(libdir)

    (path / "module3.py").touch()
    (path / "module4.py").touch()

    (path / "bye_pyodide.py").write_text("def bye(): return 'bye'")

    yield libdir

def test_defaultfilterfunc(temp_python_lib):
    ignored = ["test", "turtle.py"]
    filterfunc = default_filterfunc(
        temp_python_lib, excludes=ignored, stubs=[], verbose=True
    )

    assert set(ignored) == filterfunc(str(temp_python_lib), ignored)

    assert set() == filterfunc(str(temp_python_lib), ["hello.py", "world.py"])


def test_create_zip(temp_python_lib, tmp_path):
    from zipfile import ZipFile

    output = tmp_path / "python.zip"

    create_zipfile(
        [temp_python_lib],
        excludes=[],
        stubs=[],
        output=output,
        filterfunc=None,
    )

    assert output.exists()

    with ZipFile(output) as zf:
        assert "module1.py" in zf.namelist()
        assert "module2.py" in zf.namelist()


def test_import_from_zip(temp_python_lib, temp_python_lib2, tmp_path, monkeypatch):
    output = tmp_path / "python.zip"

    create_zipfile(
        [temp_python_lib, temp_python_lib2],
        excludes=[],
        stubs=[],
        output=output,
        filterfunc=None,
    )

    assert output.exists()

    import sys

    monkeypatch.setattr(sys, "path", [str(output)])

    import hello_pyodide

    assert hello_pyodide.__file__.startswith(str(output))
    assert hello_pyodide.hello() == "hello"

    import bye_pyodide

    assert bye_pyodide.__file__.startswith(str(output))
    assert bye_pyodide.bye() == "bye"