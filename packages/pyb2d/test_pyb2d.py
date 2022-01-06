import pytest


@pytest.mark.driver_timeout(40)
def test_pyb2d(selenium_standalone, request):
    selenium = selenium_standalone
    selenium.load_package("pyb2d")

    selenium.run(
        """
        import numpy as np
        import b2d
        w = b2d.world(gravity=(0,-10))
        """
    )
