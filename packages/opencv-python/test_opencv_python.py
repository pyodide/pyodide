# flake8: noqa
# mypy: disable-error-code=attr-defined

import pathlib
from ast import Compare

import pytest
from pytest_pyodide import run_in_pyodide

REFERENCE_IMAGES_PATH = pathlib.Path(__file__).parent / "test_data"


def compare_func_handle(selenium):
    @run_in_pyodide(packages=["opencv-python"])
    def prepare(selenium):
        import cv2 as cv
        import numpy as np
        from pytest_pyodide.decorator import PyodideHandle

        def compare(ref, image, colormode):
            DIFF_THRESHOLD = 2
            MIN_MATCH_RATIO = 0.95

            arr = np.frombuffer(ref, np.uint8)
            ref_image = cv.imdecode(arr, colormode)

            pixels_match = np.count_nonzero(
                np.abs(image.astype(np.int16) - ref_image.astype(np.int16))
                <= DIFF_THRESHOLD
            )
            pixels_total = image.size

            match_ratio = float(pixels_match / pixels_total)
            assert match_ratio > MIN_MATCH_RATIO

        return PyodideHandle(compare)

    handle = prepare(selenium)
    return handle


@run_in_pyodide(packages=["opencv-python", "numpy"])
def test_image_extensions(selenium):
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
        "tiff": b"\x49\x49\x2a\x00",
    }

    for ext, signature in extensions.items():
        result, buf = cv.imencode(f".{ext}", img)
        assert result
        assert bytes(buf[:4]) == signature


@run_in_pyodide(packages=["opencv-python", "numpy"])
def test_io(selenium):
    import cv2 as cv
    import numpy as np

    shape = (16, 16, 3)
    img = np.zeros(shape, np.uint8)

    filename = "test.bmp"
    cv.imwrite(filename, img)
    img_ = cv.imread(filename)
    assert img_.shape == img.shape


@run_in_pyodide(packages=["opencv-python", "numpy"])
def test_drawing(selenium):
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
def test_pixel_access(selenium):
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
def test_image_processing(selenium):
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
    @run_in_pyodide(packages=["opencv-python"])
    def run(selenium, comp, img, ref_sobel, ref_laplacian, ref_canny):
        import cv2 as cv
        import numpy as np

        src = np.frombuffer(img, np.uint8)
        src = cv.imdecode(src, cv.IMREAD_COLOR)
        gray = cv.cvtColor(src, cv.COLOR_BGR2GRAY)

        sobel = cv.Sobel(gray, cv.CV_8U, 1, 0, 3)
        laplacian = cv.Laplacian(gray, cv.CV_8U, ksize=3)
        canny = cv.Canny(src, 100, 255)

        comp(ref_sobel, sobel, cv.IMREAD_GRAYSCALE)
        comp(ref_laplacian, laplacian, cv.IMREAD_GRAYSCALE)
        comp(ref_canny, canny, cv.IMREAD_GRAYSCALE)

    original_img = (REFERENCE_IMAGES_PATH / "baboon.png").read_bytes()
    ref_sobel = (REFERENCE_IMAGES_PATH / "baboon_sobel.png").read_bytes()
    ref_laplacian = (REFERENCE_IMAGES_PATH / "baboon_laplacian.png").read_bytes()
    ref_canny = (REFERENCE_IMAGES_PATH / "baboon_canny.png").read_bytes()

    compare_func = compare_func_handle(selenium)
    run(selenium, compare_func, original_img, ref_sobel, ref_laplacian, ref_canny)


def test_photo_decolor(selenium):
    @run_in_pyodide(packages=["opencv-python"])
    def run(selenium, comp, img, ref_grayscale, ref_color_boost):
        import cv2 as cv
        import numpy as np

        src = np.frombuffer(img, np.uint8)
        src = cv.imdecode(src, cv.IMREAD_COLOR)

        grayscale, color_boost = cv.decolor(src)

        comp(ref_grayscale, grayscale, cv.IMREAD_GRAYSCALE)
        comp(ref_color_boost, color_boost, cv.IMREAD_COLOR)

    original_img = (REFERENCE_IMAGES_PATH / "baboon.png").read_bytes()
    ref_grayscale = (
        REFERENCE_IMAGES_PATH / "baboon_decolor_grayscale.png"
    ).read_bytes()
    ref_color_boost = (
        REFERENCE_IMAGES_PATH / "baboon_decolor_color_boost.png"
    ).read_bytes()

    compare_func = compare_func_handle(selenium)
    run(selenium, compare_func, original_img, ref_grayscale, ref_color_boost)


def test_stitch(selenium):
    @run_in_pyodide(packages=["opencv-python"])
    def run(selenium, img1, img2):
        import cv2 as cv
        import numpy as np

        left = np.frombuffer(img1, np.uint8)
        left = cv.imdecode(left, cv.IMREAD_COLOR)
        right = np.frombuffer(img2, np.uint8)
        right = cv.imdecode(right, cv.IMREAD_COLOR)
        stitcher = cv.Stitcher.create(cv.Stitcher_PANORAMA)
        status, panorama = stitcher.stitch([left, right])

        # It seems that the result is not always the same due to the randomness, so check the status and size instead
        assert status == cv.Stitcher_OK
        assert panorama.shape[0] >= max(left.shape[0], right.shape[0])
        assert panorama.shape[1] >= max(left.shape[1], right.shape[1])

    original_img_left = (REFERENCE_IMAGES_PATH / "mountain1.png").read_bytes()
    original_img_right = (REFERENCE_IMAGES_PATH / "mountain2.png").read_bytes()

    run(selenium, original_img_left, original_img_right)


def test_video_optical_flow(selenium):
    @run_in_pyodide(packages=["opencv-python"])
    def run(selenium, comp, src, ref_optical_flow):
        import cv2 as cv
        import numpy as np

        video_path = "video.mp4"
        with open(video_path, "wb") as f:
            f.write(src)

        cap = cv.VideoCapture(video_path)
        assert cap.isOpened()

        # params for ShiTomasi corner detection
        feature_params = dict(
            maxCorners=100, qualityLevel=0.3, minDistance=7, blockSize=7
        )
        # Parameters for lucas kanade optical flow
        lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv.TERM_CRITERIA_EPS | cv.TERM_CRITERIA_COUNT, 10, 0.03),
        )

        # Take first frame and find corners in it
        ret, old_frame = cap.read()
        assert ret

        old_gray = cv.cvtColor(old_frame, cv.COLOR_BGR2GRAY)
        p0 = cv.goodFeaturesToTrack(old_gray, mask=None, **feature_params)
        # Create a mask image for drawing purposes
        mask = np.zeros_like(old_frame)
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
            # calculate optical flow
            p1, st, err = cv.calcOpticalFlowPyrLK(
                old_gray, frame_gray, p0, None, **lk_params
            )
            # Select good points
            if p1 is not None:
                good_new = p1[st == 1]
                good_old = p0[st == 1]
            # draw the tracks
            for i, (new, old) in enumerate(zip(good_new, good_old)):
                a, b = new.ravel()
                c, d = old.ravel()
                mask = cv.line(mask, (int(a), int(b)), (int(c), int(d)), [0, 0, 255], 2)
                frame = cv.circle(frame, (int(a), int(b)), 5, [255, 0, 0], -1)
            img = cv.add(frame, mask)
            # Now update the previous frame and previous points
            old_gray = frame_gray.copy()
            p0 = good_new.reshape(-1, 1, 2)

        optical_flow = img

        comp(ref_optical_flow, optical_flow, cv.IMREAD_COLOR)

    original_img = (REFERENCE_IMAGES_PATH / "traffic.mp4").read_bytes()
    ref_optical_flow = (REFERENCE_IMAGES_PATH / "traffic_optical_flow.png").read_bytes()

    compare_func = compare_func_handle(selenium)
    run(selenium, compare_func, original_img, ref_optical_flow)


def test_flann_sift(selenium):
    @run_in_pyodide(packages=["opencv-python"])
    def run(selenium, comp, img1, img2, ref_sift):
        import cv2 as cv
        import numpy as np

        src1 = np.frombuffer(img1, np.uint8)
        src1 = cv.imdecode(src1, cv.IMREAD_GRAYSCALE)
        src2 = np.frombuffer(img2, np.uint8)
        src2 = cv.imdecode(src2, cv.IMREAD_GRAYSCALE)

        # -- Step 1: Detect the keypoints using SIFT Detector, compute the descriptors
        detector = cv.SIFT_create()
        keypoints1, descriptors1 = detector.detectAndCompute(src1, None)
        keypoints2, descriptors2 = detector.detectAndCompute(src2, None)

        # -- Step 2: Matching descriptor vectors with a FLANN based matcher
        matcher = cv.DescriptorMatcher_create(cv.DescriptorMatcher_FLANNBASED)
        knn_matches = matcher.knnMatch(descriptors1, descriptors2, 2)

        # -- Filter matches using the Lowe's ratio test
        ratio_thresh = 0.3
        good_matches = []
        for m, n in knn_matches:
            if m.distance < ratio_thresh * n.distance:
                good_matches.append(m)

        # -- Draw matches
        matches = np.empty(
            (max(src1.shape[0], src2.shape[0]), src1.shape[1] + src2.shape[1], 3),
            dtype=np.uint8,
        )
        cv.drawMatches(
            src1,
            keypoints1,
            src2,
            keypoints2,
            good_matches,
            matches,
            matchColor=[255, 0, 0],
            flags=cv.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
        )

        sift_result = cv.cvtColor(matches, cv.COLOR_BGR2GRAY)

        comp(ref_sift, sift_result, cv.IMREAD_GRAYSCALE)

    original_img_src1 = (REFERENCE_IMAGES_PATH / "box.png").read_bytes()
    original_img_src2 = (REFERENCE_IMAGES_PATH / "box_in_scene.png").read_bytes()
    ref_sift_result = (REFERENCE_IMAGES_PATH / "box_sift.png").read_bytes()

    compare_func = compare_func_handle(selenium)
    run(selenium, compare_func, original_img_src1, original_img_src2, ref_sift_result)


def test_dnn_mnist(selenium):
    """
    Run tiny MNIST classification ONNX model
    Training script: https://github.com/ryanking13/torch-opencv-mnist
    """

    @run_in_pyodide(packages=["opencv-python"])
    def run(selenium, img, model):
        import cv2 as cv
        import numpy as np

        model_weights = model
        model_weights_path = "./mnist.onnx"
        with open(model_weights_path, "wb") as f:
            f.write(model_weights)

        src = np.frombuffer(img, np.uint8)
        src = cv.imdecode(src, cv.IMREAD_GRAYSCALE)

        net = cv.dnn.readNet(model_weights_path)
        blob = cv.dnn.blobFromImage(src, 1.0, (28, 28), (0, 0, 0), False, False)

        net.setInput(blob)
        prob = net.forward()
        assert "output_0" in net.getLayerNames()
        assert np.argmax(prob) == 2

    original_img = (REFERENCE_IMAGES_PATH / "mnist_2.png").read_bytes()
    tf_model = (REFERENCE_IMAGES_PATH / "mnist.onnx").read_bytes()

    run(selenium, original_img, tf_model)


def test_ml_pca(selenium):
    @run_in_pyodide(packages=["opencv-python"])
    def run(selenium, comp, img, ref_pca):
        from math import atan2, cos, pi, sin, sqrt

        import cv2 as cv
        import numpy as np

        def drawAxis(img, p_, q_, colour, scale):
            p = list(p_)
            q = list(q_)

            angle = atan2(p[1] - q[1], p[0] - q[0])  # angle in radians
            hypotenuse = sqrt(
                (p[1] - q[1]) * (p[1] - q[1]) + (p[0] - q[0]) * (p[0] - q[0])
            )
            # Here we lengthen the arrow by a factor of scale
            q[0] = p[0] - scale * hypotenuse * cos(angle)
            q[1] = p[1] - scale * hypotenuse * sin(angle)
            cv.line(
                img,
                (int(p[0]), int(p[1])),
                (int(q[0]), int(q[1])),
                colour,
                1,
                cv.LINE_AA,
            )
            # create the arrow hooks
            p[0] = q[0] + 9 * cos(angle + pi / 4)
            p[1] = q[1] + 9 * sin(angle + pi / 4)
            cv.line(
                img,
                (int(p[0]), int(p[1])),
                (int(q[0]), int(q[1])),
                colour,
                1,
                cv.LINE_AA,
            )
            p[0] = q[0] + 9 * cos(angle - pi / 4)
            p[1] = q[1] + 9 * sin(angle - pi / 4)
            cv.line(
                img,
                (int(p[0]), int(p[1])),
                (int(q[0]), int(q[1])),
                colour,
                1,
                cv.LINE_AA,
            )

        def getOrientation(pts, img):
            sz = len(pts)
            data_pts = np.empty((sz, 2), dtype=np.float64)
            for i in range(data_pts.shape[0]):
                data_pts[i, 0] = pts[i, 0, 0]
                data_pts[i, 1] = pts[i, 0, 1]
            # Perform PCA analysis
            mean = np.empty(0)
            mean, eigenvectors, eigenvalues = cv.PCACompute2(data_pts, mean)
            # Store the center of the object
            cntr = (int(mean[0, 0]), int(mean[0, 1]))

            cv.circle(img, cntr, 3, (255, 0, 255), 2)
            p1 = (
                cntr[0] + 0.02 * eigenvectors[0, 0] * eigenvalues[0, 0],
                cntr[1] + 0.02 * eigenvectors[0, 1] * eigenvalues[0, 0],
            )
            p2 = (
                cntr[0] - 0.02 * eigenvectors[1, 0] * eigenvalues[1, 0],
                cntr[1] - 0.02 * eigenvectors[1, 1] * eigenvalues[1, 0],
            )
            drawAxis(img, cntr, p1, (0, 255, 0), 1)
            drawAxis(img, cntr, p2, (255, 255, 0), 5)
            angle = atan2(
                eigenvectors[0, 1], eigenvectors[0, 0]
            )  # orientation in radians

            return angle

        src = np.frombuffer(img, np.uint8)
        src = cv.imdecode(src, cv.IMREAD_COLOR)
        gray = cv.cvtColor(src, cv.COLOR_BGR2GRAY)

        # Convert image to binary
        _, bw = cv.threshold(gray, 50, 255, cv.THRESH_BINARY | cv.THRESH_OTSU)
        contours, _ = cv.findContours(bw, cv.RETR_LIST, cv.CHAIN_APPROX_NONE)
        for i, c in enumerate(contours):
            # Calculate the area of each contour
            area = cv.contourArea(c)
            # Ignore contours that are too small or too large
            if area < 1e2 or 1e5 < area:
                continue
            # Draw each contour only for visualisation purposes
            cv.drawContours(src, contours, i, (0, 0, 255), 2)
            # Find the orientation of each shape
            getOrientation(c, src)

        pca_result = src

        comp(ref_pca, pca_result, cv.IMREAD_COLOR)

    original_img = (REFERENCE_IMAGES_PATH / "pca.png").read_bytes()
    ref_pca = (REFERENCE_IMAGES_PATH / "pca_result.png").read_bytes()

    compare_func = compare_func_handle(selenium)
    run(selenium, compare_func, original_img, ref_pca)


def test_objdetect_face(selenium):
    @run_in_pyodide(packages=["opencv-python"])
    def run(selenium, comp, img, ref_face):
        from pathlib import Path

        import cv2 as cv
        import numpy as np

        src = np.frombuffer(img, np.uint8)
        src = cv.imdecode(src, cv.IMREAD_COLOR)
        gray = cv.cvtColor(src, cv.COLOR_BGR2GRAY)
        gray = cv.equalizeHist(gray)

        face_cascade = cv.CascadeClassifier()
        eyes_cascade = cv.CascadeClassifier()
        data_path = Path(cv.data.haarcascades)
        face_cascade.load(str(data_path / "haarcascade_frontalface_alt.xml"))
        eyes_cascade.load(str(data_path / "haarcascade_eye_tree_eyeglasses.xml"))

        faces = face_cascade.detectMultiScale(gray)
        face_detected = src.copy()
        for x, y, w, h in faces:
            center = (x + w // 2, y + h // 2)
            face_detected = cv.ellipse(
                face_detected, center, (w // 2, h // 2), 0, 0, 360, (255, 0, 255), 4
            )
            faceROI = gray[y : y + h, x : x + w]
            eyes = eyes_cascade.detectMultiScale(faceROI)
            for x2, y2, w2, h2 in eyes:
                eye_center = (x + x2 + w2 // 2, y + y2 + h2 // 2)
                radius = int(round((w2 + h2) * 0.25))
                face_detected = cv.circle(
                    face_detected, eye_center, radius, (255, 0, 0), 4
                )

        comp(ref_face, face_detected, cv.IMREAD_COLOR)

    original_img = (REFERENCE_IMAGES_PATH / "monalisa.png").read_bytes()
    ref_face = (REFERENCE_IMAGES_PATH / "monalisa_facedetect.png").read_bytes()

    compare_func = compare_func_handle(selenium)
    run(selenium, compare_func, original_img, ref_face)


def test_feature2d_kaze(selenium):
    @run_in_pyodide(packages=["opencv-python"])
    def run(selenium, comp, img, ref_kaze):
        import cv2 as cv
        import numpy as np

        src = np.frombuffer(img, np.uint8)
        src = cv.imdecode(src, cv.IMREAD_COLOR)

        detector = cv.KAZE_create()
        keypoints = detector.detect(src)

        kaze = cv.drawKeypoints(
            src,
            keypoints,
            None,
            color=(0, 0, 255),
            flags=cv.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS,
        )

        comp(ref_kaze, kaze, cv.IMREAD_COLOR)

    original_img = (REFERENCE_IMAGES_PATH / "baboon.png").read_bytes()
    ref_kaze = (REFERENCE_IMAGES_PATH / "baboon_kaze.png").read_bytes()

    compare_func = compare_func_handle(selenium)
    run(selenium, compare_func, original_img, ref_kaze)


def test_calib3d_chessboard(selenium):
    @run_in_pyodide(packages=["opencv-python"])
    def run(selenium, comp, img, ref_chessboard):
        import cv2 as cv
        import numpy as np

        src = np.frombuffer(img, np.uint8)
        src = cv.imdecode(src, cv.IMREAD_COLOR)

        criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        gray = cv.cvtColor(src, cv.COLOR_BGR2GRAY)
        ret, corners = cv.findChessboardCorners(gray, (9, 6), None)
        cv.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        cv.drawChessboardCorners(gray, (9, 6), corners, ret)
        chessboard_corners = gray

        comp(ref_chessboard, chessboard_corners, cv.IMREAD_GRAYSCALE)

    original_img = (REFERENCE_IMAGES_PATH / "chessboard.png").read_bytes()
    ref_chessboard = (REFERENCE_IMAGES_PATH / "chessboard_corners.png").read_bytes()

    compare_func = compare_func_handle(selenium)
    run(selenium, compare_func, original_img, ref_chessboard)
