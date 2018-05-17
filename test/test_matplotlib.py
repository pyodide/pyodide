def test_matplotlib(selenium):
    selenium.load_package("matplotlib")
    selenium.run("from matplotlib import pyplot as plt")
    selenium.run("x = plt.plot([1,2,3])")
    img = selenium.run(
        "plt.gcf()._repr_html_().src"
    )
    assert img.startswith('data:image/png;base64,')
    assert len(img) == 26766
