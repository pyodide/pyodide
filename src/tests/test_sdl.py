import pytest


@pytest.mark.xfail_browsers(node="No document object")
def test_sdl_object_2D(selenium):
    selenium.run_js(
        """
        const canvas = document.createElement('canvas');
        pyodide.SDL.setCanvas2D(canvas);

        assert(() => pyodide._module.canvas === canvas);
        assert(() => pyodide.SDL.getCanvas2D() === canvas);

        pyodide.SDL.unregisterCanvas();

        assert(() => pyodide._module.canvas === undefined)
        assert(() => pyodide.SDL.getCanvas2D() === undefined);
    """
    )


@pytest.mark.xfail_browsers(node="No document object")
def test_sdl_object_3D(selenium):
    selenium.run_js(
        """
        const canvas = document.createElement('canvas');
        pyodide.SDL.setCanvas3D(canvas);

        assert(() => pyodide._module.canvas === canvas);
        assert(() => pyodide.SDL.getCanvas3D() === canvas);

        pyodide.SDL.unregisterCanvas();

        assert(() => pyodide._module.canvas === undefined)
        assert(() => pyodide.SDL.getCanvas3D() === undefined);
    """
    )
