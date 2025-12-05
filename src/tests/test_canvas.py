import pytest


@pytest.mark.xfail_browsers(node="No document object")
def test_canvas2D(selenium_standalone_refresh):
    selenium_standalone_refresh.run_js(
        """
        const canvas = document.createElement('canvas');
        canvas.id = "canvas";

        // Temporary workaround for pyodide#3697
        pyodide._api._skip_unwind_fatal_error = true;

        pyodide.canvas.setCanvas2D(canvas);

        assert(() => pyodide._module.canvas === canvas);
        assert(() => pyodide.canvas.getCanvas2D() === canvas);
    """
    )


@pytest.mark.xfail_browsers(node="No document object")
def test_canvas3D(selenium_standalone_refresh):
    selenium_standalone_refresh.run_js(
        """
        const canvas = document.createElement('canvas');
        canvas.id = "canvas";

        // Temporary workaround for pyodide#3697
        pyodide._api._skip_unwind_fatal_error = true;

        pyodide.canvas.setCanvas3D(canvas);

        assert(() => pyodide._module.canvas === canvas);
        assert(() => pyodide.canvas.getCanvas3D() === canvas);
    """
    )
