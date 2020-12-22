def test_imageio(selenium):
    selenium.load_package(["numpy", "imageio"])
    selenium.run(
        r"""
import numpy as np
import imageio

filename = "/tmp/foo.tif"
image_in = np.random.randint(0, 65535, size=(100, 36), dtype=np.uint16)
imageio.imwrite(filename, image_in)
image_out = imageio.imread(filename)
assert image_out.shape == (100, 36)
np.testing.assert_equal(image_in, image_out)
    """
    )
