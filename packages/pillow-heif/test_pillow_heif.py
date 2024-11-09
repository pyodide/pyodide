import base64
import pathlib

from pytest_pyodide import run_in_pyodide

DEMO_PATH = pathlib.Path(__file__).parent / "test_data"
SAMPLE_IMAGE = base64.b64encode(
    (DEMO_PATH / "tree-with-transparency.heic").read_bytes()
)


def test_heif(selenium):
    @run_in_pyodide(packages=["Pillow", "pillow_heif"])
    def _test_heif_inner(selenium, image_base64):
        import base64

        with open("tree-with-transparency.heic", "wb") as f:
            f.write(base64.b64decode(image_base64))

        import pillow_heif

        if pillow_heif.is_supported("tree-with-transparency.heic"):
            heif_file = pillow_heif.open_heif(
                "tree-with-transparency.heic", convert_hdr_to_8bit=False
            )
            assert heif_file.mode == "RGBA"

    _test_heif_inner(selenium, SAMPLE_IMAGE)


def test_pillow(selenium):
    @run_in_pyodide(packages=["Pillow", "pillow_heif"])
    def _test_pillow_inner(selenium, image_base64):
        import base64

        with open("tree-with-transparency.heic", "wb") as f:
            f.write(base64.b64decode(image_base64))

        from PIL import Image
        from pillow_heif import register_heif_opener

        register_heif_opener()

        im = Image.open("tree-with-transparency.heic")
        assert im.size == (262, 264)
        assert im.mode == "RGBA"

    _test_pillow_inner(selenium, SAMPLE_IMAGE)
