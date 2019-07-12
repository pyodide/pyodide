import pytest
import os
import pathlib
from selenium.webdriver.support.wait import WebDriverWait

TEST_PATH = pathlib.Path(__file__).parents[0].resolve()


def get_canvas_data(selenium, prefix):
    import base64
    canvas_tag_property = "//canvas[starts-with(@id, 'matplotlib')]"
    canvas_element = selenium.driver.find_element_by_xpath(canvas_tag_property)
    img_script = "return arguments[0].toDataURL('image/png').substring(21)"
    canvas_base64 = selenium.driver.execute_script(img_script, canvas_element)
    canvas_png = base64.b64decode(canvas_base64)
    with open(TEST_PATH /
              r"{0}-{1}.png".format(prefix, selenium.browser), 'wb') as f:
        f.write(canvas_png)


def check_comparison(selenium, prefix):
    # If we don't have a reference image, write one to disk
    if not os.path.isfile('test/{0}-{1}.png'.format(prefix, selenium.browser)):
        get_canvas_data(selenium, prefix)

    selenium.run("""
    url = 'test/{0}-{1}.png'
    threshold = 0
    plt.gcf().canvas.compare_reference_image(url, threshold)
    """.format(prefix, selenium.browser))

    wait = WebDriverWait(selenium.driver, timeout=70)
    wait.until(ResultLoaded())
    assert selenium.run("window.deviation") == 0
    assert selenium.run("window.result") is True


@pytest.mark.skip_refcount_check
def test_matplotlib(selenium_standalone):
    selenium = selenium_standalone
    selenium.load_package("matplotlib")
    selenium.run(
        """
        from matplotlib import pyplot as plt
        plt.figure()
        plt.plot([1,2,3])
        plt.show()
        """
    )


@pytest.mark.skip_refcount_check
def test_svg(selenium):
    selenium.load_package("matplotlib")
    selenium.run("from matplotlib import pyplot as plt")
    selenium.run("plt.figure(); pass")
    selenium.run("x = plt.plot([1,2,3])")
    selenium.run("import io")
    selenium.run("fd = io.BytesIO()")
    selenium.run("plt.savefig(fd, format='svg')")
    content = selenium.run("fd.getvalue().decode('utf8')")
    assert len(content) == 16283
    assert content.startswith("<?xml")


def test_pdf(selenium):
    selenium.load_package("matplotlib")
    selenium.run("from matplotlib import pyplot as plt")
    selenium.run("plt.figure(); pass")
    selenium.run("x = plt.plot([1,2,3])")
    selenium.run("import io")
    selenium.run("fd = io.BytesIO()")
    selenium.run("plt.savefig(fd, format='pdf')")


def test_font_manager(selenium):
    """
    Comparing vendored fontlist.json version with the one built
    by font_manager.py.

    If you try to update Matplotlib and this test fails, try to
    update fontlist.json.
    """
    selenium.load_package("matplotlib")
    selenium.run(
        """
        from matplotlib import font_manager as fm
        import os
        import json

        # get fontlist form file
        fontist_file = os.path.join(os.path.dirname(fm.__file__), 'fontlist.json')
        with open(fontist_file) as f:
            fontlist_vendor = json.loads(f.read())

        # get fontlist from build
        fontlist_built = json.loads(json.dumps(fm.FontManager(), cls=fm._JSONEncoder))

        # reodering list to compare
        for list in ('afmlist', 'ttflist'):
            for fontlist in (fontlist_vendor, fontlist_built):
                fontlist[list].sort(key=lambda x: x['fname'])
        """
    )
    assert selenium.run("fontlist_built == fontlist_vendor")


def test_rendering(selenium):
    selenium.load_package("matplotlib")
    selenium.run("""
    from js import window
    window.testing = True
    from matplotlib import pyplot as plt
    import numpy as np
    t = np.arange(0.0, 2.0, 0.01)
    s = 1 + np.sin(2 * np.pi * t)
    plt.figure()
    plt.plot(t, s, linewidth=1.0, marker=11)
    plt.plot(t, t)
    plt.grid(True)
    plt.show()
    """)

    check_comparison(selenium, 'canvas')


def test_draw_image(selenium):
    selenium.load_package("matplotlib")
    selenium.run("""
    from js import window
    window.testing = True
    import numpy as np
    import matplotlib.cm as cm
    import matplotlib.pyplot as plt
    import matplotlib.cbook as cbook
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    delta = 0.025
    x = y = np.arange(-3.0, 3.0, delta)
    X, Y = np.meshgrid(x, y)
    Z1 = np.exp(-X**2 - Y**2)
    Z2 = np.exp(-(X - 1)**2 - (Y - 1)**2)
    Z = (Z1 - Z2) * 2
    plt.figure()
    plt.imshow(Z, interpolation='bilinear', cmap=cm.RdYlGn,
               origin='lower', extent=[-3, 3, -3, 3],
               vmax=abs(Z).max(), vmin=-abs(Z).max())
    plt.show()
    """)

    check_comparison(selenium, 'canvas-image')


def test_draw_image_affine_transform(selenium):
    selenium.load_package("matplotlib")
    selenium.run("""
    from js import window
    window.testing = True

    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.transforms as mtransforms

    def get_image():
        delta = 0.25
        x = y = np.arange(-3.0, 3.0, delta)
        X, Y = np.meshgrid(x, y)
        Z1 = np.exp(-X**2 - Y**2)
        Z2 = np.exp(-(X - 1)**2 - (Y - 1)**2)
        Z = (Z1 - Z2)
        return Z

    def do_plot(ax, Z, transform):
        im = ax.imshow(Z, interpolation='none',
                    origin='lower',
                    extent=[-2, 4, -3, 2], clip_on=True)

        trans_data = transform + ax.transData
        im.set_transform(trans_data)

        # display intended extent of the image
        x1, x2, y1, y2 = im.get_extent()
        ax.plot([x1, x2, x2, x1, x1], [y1, y1, y2, y2, y1], "y--",
                transform=trans_data)
        ax.set_xlim(-5, 5)
        ax.set_ylim(-4, 4)

    # prepare image and figure
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2)
    Z = get_image()

    # image rotation
    do_plot(ax1, Z, mtransforms.Affine2D().rotate_deg(30))

    # image skew
    do_plot(ax2, Z, mtransforms.Affine2D().skew_deg(30, 15))

    # scale and reflection
    do_plot(ax3, Z, mtransforms.Affine2D().scale(-1, .5))

    # everything and a translation
    do_plot(ax4, Z, mtransforms.Affine2D().
            rotate_deg(30).skew_deg(30, 15).scale(-1, .5).translate(.5, -1))

    plt.show()
    """)

    check_comparison(selenium, 'canvas-image-affine')


class ResultLoaded:
    def __call__(self, driver):
        inited = driver.execute_script("return window.result")
        return inited is not None
