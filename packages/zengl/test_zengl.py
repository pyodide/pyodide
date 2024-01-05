import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.driver_timeout(60)
@pytest.mark.xfail_browsers(node="this supposed to render into a canvas DOM element")
@run_in_pyodide(packages=["zengl"])
def test_render_with_webgl2(selenium):
    import zengl

    import js

    canvas = js.document.createElement("canvas")
    canvas.id = "canvas"
    canvas.width = 320
    canvas.height = 240

    canvas.style.position = "fixed"
    canvas.style.bottom = "10px"
    canvas.style.right = "10px"

    gl = canvas.getContext(
        "webgl2",
        powerPreference="high-performance",
        premultipliedAlpha=False,
        antialias=False,
        alpha=False,
        depth=False,
        stencil=False,
    )
    js.document.body.appendChild(canvas)

    if gl:
        zengl.context()
