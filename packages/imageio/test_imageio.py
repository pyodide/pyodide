from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(standalone=True, packages=["numpy", "imageio"])
def test_imageio():
    import imageio
    import numpy as np

    filename = "/tmp/foo.tif"
    image_in = np.random.randint(0, 65535, size=(100, 36), dtype=np.uint16)
    imageio.imwrite(filename, image_in)
    image_out = imageio.imread(filename)
    assert image_out.shape == (100, 36)
    np.testing.assert_equal(image_in, image_out)


@run_in_pyodide(packages=["numpy", "imageio"])
def test_jpg():
    import imageio
    import numpy as np

    img = np.zeros((5, 5), dtype=np.uint8)
    imageio.imsave("img.jpg", img)
    assert (imageio.imread("img.jpg") == img).all()
