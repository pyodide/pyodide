import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
@run_in_pyodide(packages=["pyxel"])
def test_basic(selenium):

    import pyodide

    pyodide.run_js(
        """
        var sdl2Canvas = document.createElement("canvas");
        sdl2Canvas.id = "canvas";
        sdl2Canvas.tabindex = -1;

        document.body.appendChild(sdl2Canvas);
        pyodide._module.canvas = document.querySelector("#canvas");
        """
    )

    import pyxel

    class App:
        def __init__(self):
            pyxel.init(160, 120, title="Hello Pyxel")
            pyxel.image(0).load(0, 0, "assets/pyxel_logo_38x16.png")
            pyxel.run(self.update, self.draw)

        def update(self):
            if pyxel.btnp(pyxel.KEY_Q):
                pyxel.quit()

        def draw(self):
            pyxel.cls(0)
            pyxel.text(55, 41, "Hello, Pyxel!", pyxel.frame_count % 16)
            pyxel.blt(61, 66, 0, 0, 0, 38, 16)

    App()
