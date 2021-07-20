from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(
    packages=["pillow"],
    xfail_browsers={"firefox": "timeout", "chrome": "", "node": "timeout"},
)
def test_pillow():
    from PIL import Image, ImageDraw, ImageOps
    import io

    img = Image.new("RGB", (4, 4), color=(0, 0, 0))
    ctx = ImageDraw.Draw(img)
    ctx.line([0, 0, 3, 0, 3, 3, 0, 3, 0, 0], (255, 0, 0), 1)
    img.putpixel((1, 1), (0, 255, 0))
    img.putpixel((2, 2), (0, 0, 255))
    img = ImageOps.flip(img)
    assert (
        img.tobytes()
        == b"\xff\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\xff\xff\x00\x00\xff\x00\x00\x00\xff\x00\x00\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00"
    )
    with io.BytesIO() as byio:
        img.save(byio, format="PNG")

        assert (
            byio.getvalue()
            == b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x04\x00\x00\x00\x04\x08\x02\x00\x00\x00&\x93\t)\x00\x00\x00\x1cIDATx\x9cc\xfc\xcf\x80\x04`\x9c\xff\xff\x19\x18\x98`\x02\x8c\x0c\x0c\x0c\x8c\xc8\xca\x00\xb5\x05\x06\x00\xcbi8B\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        img = Image.open(byio)
        assert (
            img.tobytes()
            == b"\xff\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00\x00\x00\x00\x00\x00\xff\xff\x00\x00\xff\x00\x00\x00\xff\x00\x00\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00\xff\x00\x00"
        )

    with io.BytesIO() as asjpg:
        img.save(asjpg, format="JPEG")
        img = Image.open(asjpg)
