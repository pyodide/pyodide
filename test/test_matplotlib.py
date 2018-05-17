def test_matplotlib(selenium):
    selenium.load_package("matplotlib")
    img = selenium.run(
        "from matplotlib import pyplot as plt\n"
        "plt.plot([1,2,3])\n"
        "plt.gcf()._repr_html_().src"
    )
    assert img.startswith('data:image/png;base64,')
    assert len(img) == 42
