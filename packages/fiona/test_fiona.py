import base64
import pathlib

import pytest

DEMO_PATH = pathlib.Path(__file__).parent / "test_data"
DATA_TEST = base64.b64encode((DEMO_PATH / "coutwildrnp.shp").read_bytes())


@pytest.mark.driver_timeout(60)
def test_basic_classification(selenium):
    selenium.load_package("fiona")
    selenium.run(
        f"""
        import base64
        with open("coutwildrnp.shp", "wb") as f:
            f.write(base64.b64decode({DATA_TEST!r}))


        import fiona
        with fiona.open('coutwildrnp.shp') as src:
            print(src[0])
            print(len(src))
        """
    )
