from pytest_pyodide.decorator import run_in_pyodide


@run_in_pyodide(packages=["packaging"])
def test_packaging(selenium):
    import re

    from packaging.tags import platform_tags

    tags = sorted(re.sub(r"[0-9]+", "x", t) for t in platform_tags())
    assert tags == [
        "emscripten_x_x_x_wasmx",
        "pyemscripten_x_x_wasmx",
        "pyodide_x_x_wasmx",
    ]
