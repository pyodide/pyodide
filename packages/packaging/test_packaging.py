from pytest_pyodide.decorator import run_in_pyodide


@run_in_pyodide(packages=["packaging"])
def test_packaging(selenium):
    from packaging.tags import platform_tags

    assert sorted(platform_tags()) == [
        "emscripten_5_0_3_wasm32",
        "pyemscripten_2026_0_wasm32",
    ]
