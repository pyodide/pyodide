import pytest


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
    selenium_standalone.load_package("pyxel")
    yield selenium_standalone


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_show(selenium_sdl):
    selenium_sdl.run(
        """
        import pyxel

        pyxel.init(120, 120)
        pyxel.cls(1)
        pyxel.circb(60, 60, 40, 7)
        pyxel.show()
        """
    )


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_run(selenium_sdl):
    selenium_sdl.run(
        """
        import time
        import pyxel

        pyxel.init(160, 120)

        st = time.time()

        def update():
            cur = time.time()
            if cur - st > 2:
                pyxel.quit()

        def draw():
            pyxel.cls(0)
            pyxel.rect(10, 10, 20, 20, 11)

        pyxel.run(update, draw)
        """
    )
