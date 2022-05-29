from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(
    packages=["Pillow"],
)
def test_pillow(selenium):
    import io

    from PIL import Image, ImageDraw, ImageOps

    img = Image.new("RGB", (4, 4), color=(0, 0, 0))
    ctx = ImageDraw.Draw(img)
    ctx.line([0, 0, 3, 0, 3, 3, 0, 3, 0, 0], (255, 0, 0), 1)
    img.putpixel((1, 1), (0, 255, 0))
    img.putpixel((2, 2), (0, 0, 255))
    img = ImageOps.flip(img)

    img_bytes = b"\xff\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\xff\xff\x00\x00\xff\x00\x00\x00\xff\x00\x00\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00"
    assert img.tobytes() == img_bytes

    extensions = {
        "jpeg": b"\xff\xd8\xff\xe0",
        "png": b"\x89PNG",
        "webp": b"RIFF",
    }

    for ext, signature in extensions.items():
        with io.BytesIO() as imgfile:
            img.save(imgfile, format=ext.upper())
            _img = Image.open(imgfile)
            assert _img
            assert (
                imgfile.getvalue()[:4] == signature
            ), f"Wrong signature on image format: {ext}"


@run_in_pyodide(
    packages=["Pillow"],
)
def test_jpeg_modes(selenium):
    from PIL import Image

    rgb = Image.new("RGB", (4, 4))
    rgb.save("rgb.jpg")

    gray = Image.new("L", (4, 4))
    gray.save("gray.jpg")

    bw = Image.new("1", (4, 4))
    bw.save("bw.jpg")
