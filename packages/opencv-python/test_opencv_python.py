from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(
    packages=["opencv-python"],
)
def test_cv2():
    import cv2

    cv2
