import pytest


@pytest.mark.driver_timeout(40)
def test_pybox2d(selenium_standalone, request):
    selenium = selenium_standalone
    selenium.load_package("pybox2d")
    assert (
        selenium.run(
            """
        import numpy as np
        import pybox2d
        w = pybox2d.world(gravity=(0,-10))
        """
        )
        > 0
    )
