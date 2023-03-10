import pytest


@pytest.mark.xfail_browsers(node="No document object")
def test_canvas2D(selenium):
    selenium.run_js(
        """
        const canvas = document.createElement('canvas');
        canvas.id = "canvas";
        pyodide.canvas.setCanvas2D(canvas);

        assert(() => pyodide._module.canvas === canvas);
        assert(() => pyodide.canvas.getCanvas2D() === canvas);
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
    """
    )
