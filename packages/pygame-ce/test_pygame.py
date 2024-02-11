import pytest
from pytest_pyodide import run_in_pyodide


@pytest.fixture(scope="function")
def selenium_sdl(selenium_standalone):
    if selenium_standalone.browser == "node":
        pytest.skip("No document object")

    selenium_standalone.run_js(
        """
        var sdl2Canvas = document.createElement("canvas");
        sdl2Canvas.id = "canvas";

        document.body.appendChild(sdl2Canvas);
        // Temporary workaround for pyodide#3697
        pyodide._api._skip_unwind_fatal_error = true;
        pyodide.canvas.setCanvas2D(sdl2Canvas);
        """
    )
    yield selenium_standalone


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
@run_in_pyodide(packages=["pygame-ce"])
def test_init(selenium_sdl):
    import pygame.display
    pygame.display.init()
