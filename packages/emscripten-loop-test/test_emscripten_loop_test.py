from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["emscripten-loop-test"])
def test_emscripten_loop(selenium):
    import emscripten_loop_test

    assert emscripten_loop_test.get_counter() == 0

    emscripten_loop_test.main_loop()

    assert emscripten_loop_test.get_counter() == 100
