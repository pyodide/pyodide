import base64
import pathlib

from pyodide_build.testing import run_in_pyodide

REFERENCE_IMAGES_PATH = pathlib.Path(__file__).parent / "reference-images"


def compare_with_reference_image(selenium, reference_image, var="img", grayscale=True):
    reference_image_encoded = base64.b64encode(reference_image.read_bytes())
    grayscale = "cv.IMREAD_GRAYSCALE" if grayscale else "cv.IMREAD_COLOR"
    deviation = selenium.run(
        f"""
        import base64
        import numpy as np
        import cv2 as cv
        arr = np.frombuffer(base64.b64decode({reference_image_encoded!r}), np.uint8)
        ref_data = cv.imdecode(arr, {grayscale})

        deviation = np.mean(np.abs({var} - ref_data))
        float(deviation)
        """
    )

    return deviation == 0.0


@run_in_pyodide(packages=["opencv-python"])
def test_import():
    import cv2

    print(f"{cv2.__version__=}")
    print(f"{cv2.getBuildInformation()=}")


@run_in_pyodide(packages=["opencv-python", "numpy"])
def test_image_extensions():
    import cv2 as cv
    import numpy as np

    shape = (16, 16, 3)
    img = np.zeros(shape, np.uint8)

    extensions = {
        "bmp": b"BM6\x03",
        "jpg": b"\xff\xd8\xff\xe0",
        "jpeg": b"\xff\xd8\xff\xe0",
        "png": b"\x89PNG",
        "webp": b"RIFF",
    }

    for ext, signature in extensions.items():
        result, buf = cv.imencode(f".{ext}", img)
        assert result
        assert bytes(buf[:4]) == signature


@run_in_pyodide(packages=["opencv-python", "numpy"])
def test_io():
    import cv2 as cv
    import numpy as np

    shape = (16, 16, 3)
    img = np.zeros(shape, np.uint8)

    filename = "test.bmp"
    cv.imwrite(filename, img)
    img_ = cv.imread(filename)
    assert img_.shape == img.shape


@run_in_pyodide(packages=["opencv-python", "numpy"])
def test_drawing():
    import cv2 as cv
    import numpy as np

    width = 100
    height = 100
    shape = (width, height, 3)
    img = np.zeros(shape, np.uint8)

    cv.line(img, (0, 0), (width - 1, 0), (255, 0, 0), 5)
    cv.line(img, (0, 0), (0, height - 1), (0, 0, 255), 5)
    cv.rectangle(img, (0, 0), (width // 2, height // 2), (0, 255, 0), 2)
    cv.circle(img, (0, 0), radius=width // 2, color=(255, 0, 0))
    cv.putText(img, "Hello Pyodide", (0, 0), cv.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)


@run_in_pyodide(packages=["opencv-python", "numpy"])
def test_pixel_access():
    import cv2 as cv
    import numpy as np

    shape = (16, 16, 3)
    img = np.zeros(shape, np.uint8)

    img[5, 5] = [1, 2, 3]
    assert list(img[5, 5]) == [1, 2, 3]

    b, g, r = cv.split(img)
    img_ = cv.merge([b, g, r])
    assert (img == img_).all()


@run_in_pyodide(packages=["opencv-python", "numpy"])
def test_image_processing():
    import cv2 as cv
    import numpy as np

    # Masking
    img = np.random.randint(0, 255, size=500)
    lower = np.array([0])
    upper = np.array([200])
    mask = cv.inRange(img, lower, upper)
    res = cv.bitwise_and(img, img, mask=mask)
    assert not (res > 200).any()


def test_edge_detection(selenium):
    original_img = base64.b64encode((REFERENCE_IMAGES_PATH / "baboon.png").read_bytes())
    selenium.load_package("opencv-python")
    selenium.run(
        f"""
        import base64
        import cv2 as cv
        import numpy as np
        src = np.frombuffer(base64.b64decode({original_img!r}), np.uint8)
        src = cv.imdecode(src, cv.IMREAD_COLOR)
        gray = cv.cvtColor(src, cv.COLOR_BGR2GRAY)
        sobel = cv.Sobel(gray, cv.CV_8U, 1, 0, 3)
        laplacian = cv.Laplacian(gray, cv.CV_8U, ksize=3)
        canny = cv.Canny(src, 100, 255)
        None
        """
    )

    assert compare_with_reference_image(
        selenium, REFERENCE_IMAGES_PATH / "baboon_sobel.png", "sobel"
    )
    assert compare_with_reference_image(
        selenium, REFERENCE_IMAGES_PATH / "baboon_laplacian.png", "laplacian"
    )
    assert compare_with_reference_image(
        selenium, REFERENCE_IMAGES_PATH / "baboon_canny.png", "canny"
    )


def test_photo(selenium):
    original_img = base64.b64encode((REFERENCE_IMAGES_PATH / "baboon.png").read_bytes())
    selenium.load_package("opencv-python")
    selenium.run(
        f"""
        import base64
        import cv2 as cv
        import numpy as np
        src = np.frombuffer(base64.b64decode({original_img!r}), np.uint8)
        src = cv.imdecode(src, cv.IMREAD_COLOR)
        grayscale, color_boost = cv.decolor(src)
        None
        """
    )

    assert compare_with_reference_image(
        selenium, REFERENCE_IMAGES_PATH / "baboon_decolor_grayscale.png", "grayscale"
    )
    assert compare_with_reference_image(
        selenium,
        REFERENCE_IMAGES_PATH / "baboon_decolor_color_boost.png",
        "color_boost",
        grayscale=False,
    )


def test_stitch(selenium):
    original_img_left = base64.b64encode(
        (REFERENCE_IMAGES_PATH / "mountain1.png").read_bytes()
    )
    original_img_right = base64.b64encode(
        (REFERENCE_IMAGES_PATH / "mountain2.png").read_bytes()
    )
    selenium.load_package("opencv-python")
    selenium.run(
        f"""
        import base64
        import cv2 as cv
        import numpy as np
        left = np.frombuffer(base64.b64decode({original_img_left!r}), np.uint8)
        left = cv.imdecode(left, cv.IMREAD_COLOR)
        right = np.frombuffer(base64.b64decode({original_img_right!r}), np.uint8)
        right = cv.imdecode(right, cv.IMREAD_COLOR)
        stitcher = cv.Stitcher.create(cv.Stitcher_PANORAMA)
        status, panorama = stitcher.stitch([left, right])

        # It seems that the result is not always the same due to the randomness, so check the status and size instead
        assert status == cv.Stitcher_OK
        assert panorama.shape[0] >= max(left.shape[0], right.shape[0])
        assert panorama.shape[1] >= max(left.shape[1], right.shape[1])
        """
    )


def test_video():
    raise NotImplementedError()


def test_flann():
    raise NotImplementedError()


def test_dnn():
    raise NotImplementedError()


def test_ml():
    raise NotImplementedError()


def test_objdetect():
    raise NotImplementedError()


def test_feature2d(selenium):
    original_img = base64.b64encode((REFERENCE_IMAGES_PATH / "baboon.png").read_bytes())
    selenium.load_package("opencv-python")
    selenium.run(
        f"""
        import base64
        import cv2 as cv
        import numpy as np
        src = np.frombuffer(base64.b64decode({original_img!r}), np.uint8)
        src = cv.imdecode(src, cv.IMREAD_COLOR)

        detector = cv.KAZE_create()
        keypoints = detector.detect(src)

        kaze = cv.drawKeypoints(src, keypoints, None, color=(0, 0, 255), flags=cv.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        None
        """
    )

    assert compare_with_reference_image(
        selenium,
        REFERENCE_IMAGES_PATH / "baboon_kaze.png",
        "kaze",
        grayscale=False,
    )


def test_calib3d(selenium):
    original_img = base64.b64encode(
        (REFERENCE_IMAGES_PATH / "chessboard.png").read_bytes()
    )
    selenium.load_package("opencv-python")
    selenium.run(
        f"""
        import base64
        import cv2 as cv
        import numpy as np
        src = np.frombuffer(base64.b64decode({original_img!r}), np.uint8)
        src = cv.imdecode(src, cv.IMREAD_COLOR)

        criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        gray = cv.cvtColor(src, cv.COLOR_BGR2GRAY)
        ret, corners = cv.findChessboardCorners(gray, (9, 6), None)
        cv.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        cv.drawChessboardCorners(gray, (9, 6), corners, ret)
        chessboard_corners = gray
        None
        """
    )

    assert compare_with_reference_image(
        selenium,
        REFERENCE_IMAGES_PATH / "chessboard_corners.png",
        "chessboard_corners",
    )
