import base64
import pathlib

DEMO_PATH = pathlib.Path(__file__).parent / "test_data"
SAMPLE_IMAGE = base64.b64encode(
    (DEMO_PATH / "tree-with-transparency.heic").read_bytes()
)


def test_heif(selenium):
    selenium.load_package(["pillow_heif"])
    selenium.run(
        f"""
        import base64
        with open("tree-with-transparency.heic", "wb") as f:
            f.write(base64.b64decode({SAMPLE_IMAGE!r}))

        import pillow_heif

        if pillow_heif.is_supported("tree-with-transparency.heic"):
            heif_file = pillow_heif.open_heif("tree-with-transparency.heic", convert_hdr_to_8bit=False)
            assert heif_file.mode == "RGBA"
            assert len(heif_file.data) == 278784
            assert heif_file.stride == 1056
        """
    )


def test_pillow(selenium):
    selenium.load_package(["Pillow", "pillow_heif"])
    selenium.run(
        f"""
        import base64
        with open("tree-with-transparency.heic", "wb") as f:
            f.write(base64.b64decode({SAMPLE_IMAGE!r}))

        from PIL import Image
        import pillow_heif
        from pillow_heif import register_heif_opener

        register_heif_opener()

        im = Image.open("tree-with-transparency.heic")
        assert im.size == (262, 264)
        assert im.mode == "RGBA"
        """
    )
