# flake8: noqa

from pyodide_build.pyzip import create_zipfile, default_filterfunc

from .fixture import temp_python_lib, temp_python_lib2


def test_defaultfilterfunc(temp_python_lib):
    filterfunc = default_filterfunc(temp_python_lib, verbose=True)

    ignored = ["test", "distutils", "turtle.py"]
    assert set(ignored) == filterfunc(str(temp_python_lib), ignored)

    assert set() == filterfunc(str(temp_python_lib), ["hello.py", "world.py"])


def test_create_zip(temp_python_lib, tmp_path):
    from zipfile import ZipFile

    output = tmp_path / "python.zip"

    create_zipfile([temp_python_lib], output, pycompile=False, filterfunc=None)

    assert output.exists()

    with ZipFile(output) as zf:
        assert "module1.py" in zf.namelist()
        assert "module2.py" in zf.namelist()


def test_create_zip_compile(temp_python_lib, tmp_path):
    from zipfile import ZipFile

    output = tmp_path / "python.zip"

    create_zipfile([temp_python_lib], output, pycompile=True, filterfunc=None)

    assert output.exists()

    with ZipFile(output) as zf:
        assert "module1.pyc" in zf.namelist()
        assert "module2.pyc" in zf.namelist()


def test_import_from_zip(temp_python_lib, temp_python_lib2, tmp_path, monkeypatch):
    output = tmp_path / "python.zip"

    create_zipfile(
        [temp_python_lib, temp_python_lib2], output, pycompile=False, filterfunc=None
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
