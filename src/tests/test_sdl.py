import pytest


@pytest.mark.xfail_browsers(node="No document object")
def test_sdl_object(selenium):
    selenium.run_js(
        """
        const canvas = document.createElement('canvas');
        pyodide.SDL.registerCanvas(canvas);

        assert(() => pyodide._module.canvas === canvas);
        assert(() => pyodide.SDL.getCanvas() === canvas);

        pyodide.SDL.unregisterCanvas();

        assert(() => pyodide._module.canvas === undefined)
        assert(() => pyodide.SDL.getCanvas() === undefined);
    """
    )
