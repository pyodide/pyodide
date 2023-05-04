from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pygame-ce"])
def test_idle(selenium):
    import pygame

    print(pygame.__version__)


@run_in_pyodide(packages=["pygame-ce"])
def test_example(selenium):
    import pygame.examples.aliens

    pygame.examples.aliens.main()
