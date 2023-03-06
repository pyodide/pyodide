import pytest
from pytest_pyodide import run_in_pyodide


@pytest.fixture(scope="function")
def selenium_sdl(selenium_standalone):
    selenium_standalone.run_js(
        """
        var sdl2Canvas = document.createElement("canvas");
        document.body.appendChild(sdl2Canvas);
        pyodide.SDL.setCanvas(sdl2Canvas);
        """
    )
    yield selenium_standalone


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
@run_in_pyodide(packages=["pyxel"])
def test_show(selenium_sdl):

    import pyxel

    pyxel.init(120, 120)
    pyxel.cls(1)
    pyxel.circb(60, 60, 40, 7)
    pyxel.show()


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
@run_in_pyodide(packages=["pyxel"])
def test_run(selenium_sdl):

    import time

    import pyxel

    pyxel.init(160, 120)

    st = time.time()

    def update():
        cur = time.time()
        if cur - st > 3:
            pyxel.quit()

    def draw():
        pyxel.cls(0)
        pyxel.rect(10, 10, 20, 20, 11)

    pyxel.run(update, draw)
