import base64
import pathlib

DEMO_PATH = pathlib.Path(__file__).parent / "test_data"
SAMPLE_IMAGE = base64.b64encode(
    (DEMO_PATH / "tree-with-transparency.heic").read_bytes()
)


def test_read(selenium):
    selenium.load_package("pyheif")
    selenium.run(
        f"""
        import base64
        with open("tree-with-transparency.heic", "wb") as f:
            f.write(base64.b64decode({SAMPLE_IMAGE!r}))

        import pyheif
        heif_file = pyheif.read("tree-with-transparency.heic")
        assert heif_file.mode == "RGBA"
        assert heif_file.size == (262, 264)
        assert heif_file.stride == 1056
        assert heif_file.bit_depth == 8
        """
    )
