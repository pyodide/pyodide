def test_matplotlib(selenium):
    selenium.load_package("matplotlib")
    selenium.run("from matplotlib import pyplot as plt")
    selenium.run("x = plt.plot([1,2,3])")
    img = selenium.run(
        "plt.gcf()._repr_html_().src"
    )
    assert img.startswith('data:image/png;base64,')
    assert len(img) == 26766


def test_svg(selenium):
    selenium.load_package("matplotlib")
    selenium.run("from matplotlib import pyplot as plt")
    selenium.run("x = plt.plot([1,2,3])")
    selenium.run("import io")
    selenium.run("fd = io.BytesIO()")
    selenium.run("plt.savefig(fd, format='svg')")
    content = selenium.run("fd.getvalue().decode('utf8')")
    assert len(content) == 15752
    assert content.startswith("<?xml")
