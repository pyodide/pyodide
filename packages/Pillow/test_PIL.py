from textwrap import dedent

import pytest


def test_bool(selenium_standalone, request):
    selenium = selenium_standalone
    selenium.load_package("Pillow")
    selenium.load_package("numpy")
    cmd = dedent(r"""
        import numpy as np
        from PIL import Image
        a = np.zeros((10, 2), dtype=np.bool)
        a[0][0] = True
        im = Image.fromarray(a)
        assert im.getdata()[0] == 255
        """)

    selenium.run(cmd)
