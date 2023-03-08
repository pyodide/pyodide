import pytest


@pytest.mark.xfail_browsers(node="No document object")
def test_canvas2D(selenium):
    selenium.run_js(
        """
        const canvas = document.createElement('canvas');
        canvas.id = "canvas";
        pyodide.canvas.setCanvas2D(canvas);

        assert(() => pyodide._module.canvas === canvas);
        assert(() => pyodide.SDL.getCanvas2D() === canvas);

        pyodide.canvas.unregisterCanvas();

        assert(() => pyodide._module.canvas === undefined)
        assert(() => pyodide.SDL.getCanvas2D() === undefined);
    """
    )


@pytest.mark.xfail_browsers(node="No document object")
def test_canvas3D(selenium):
    selenium.run_js(
        """
        const canvas = document.createElement('canvas');
        canvas.id = "canvas";
        pyodide.canvas.setCanvas3D(canvas);

        assert(() => pyodide._module.canvas === canvas);
        assert(() => pyodide.SDL.getCanvas3D() === canvas);

        pyodide.canvas.unregisterCanvas();

        assert(() => pyodide._module.canvas === undefined)
        assert(() => pyodide.SDL.getCanvas3D() === undefined);
    """
    )
