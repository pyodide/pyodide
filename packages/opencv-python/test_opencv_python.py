from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["opencv-python"])
def test_import():
    import cv2

    print(f"{cv2.__version__=}")
    print(f"{cv2.getBuildInformation()=}")


@run_in_pyodide(packages=["opencv-python", "numpy"])
def test_extensions():
    """Test writers for common extensions"""
    import cv2
    import numpy as np

    shape = (16, 16, 3)
    img = np.zeros(shape, np.uint8)

    cv2.imwrite("img.bmp", img)
    cv2.imwrite("img.jpg", img)
    cv2.imwrite("img.jpeg", img)
    cv2.imwrite("img.png", img)


@run_in_pyodide(packages=["opencv-python", "numpy"])
def test_drawing():
    import cv2
    import numpy as np

    width = 100
    height = 100
    shape = (width, height, 3)
    img = np.zeros(shape, np.uint8)

    cv2.line(img, (0, 0), (width - 1, 0), (255, 0, 0), 5)
    cv2.line(img, (0, 0), (0, height - 1), (0, 0, 255), 5)
    cv2.rectangle(img, (0, 0), (width // 2, height // 2), (0, 255, 0), 2)
    cv2.circle(img, (0, 0), radius=width // 2, color=(255, 0, 0))
    cv2.putText(
        img, "Hello Pyodide", (0, 0), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2
    )


def test_image_processing():
    raise NotImplementedError()


def test_algorithm():
    raise NotImplementedError()


def test_video():
    raise NotImplementedError()


def test_ml():
    raise NotImplementedError()
