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
        pyodide.canvas.setCanvas2D(sdl2Canvas);
        """
    )
    yield selenium_standalone


@run_in_pyodide(packages=["pygame-ce"])
def test_init(selenium_sdl):
    import pygame.display
    pygame.display.init()


def test_basic_display(selenium_sdl):
    @run_in_pyodide(packages=["pygame-ce"])

    async def run(selenium):
        import pygame
        import pygame.display

        screen = pygame.display.set_mode([100, 100])
        pygame.display.set_caption("Caption")

        # black background
        screen.fill((0, 0, 0))

        # red rectangle
        pygame.draw.rect(screen, (255, 0, 0), [30, 30, 3, 3])

        # blue circle
        pygame.draw.circle(screen, (0, 0, 255), [50, 50], 5)

        pygame.display.flip()

    run(selenium_sdl)

    selenium_sdl.run_js(
        """
        canvas = document.getElementById("canvas");
        context = canvas.getContext("2d");
        blackPixel = context.getImageData(0, 0, 1, 1).data

        assert(() => blackPixel[0] === 0)
        assert(() => blackPixel[1] === 0)
        assert(() => blackPixel[2] === 0)

        bluePixel = context.getImageData(50, 50, 1, 1).data

        assert(() => bluePixel[0] === 0)
        assert(() => bluePixel[1] === 0)
        assert(() => bluePixel[2] === 255)
        """
    )