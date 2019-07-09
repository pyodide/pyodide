import pytest
import os
import pathlib
from selenium.webdriver.support.wait import WebDriverWait

TEST_PATH = pathlib.Path(__file__).parents[0].resolve()


def get_canvas_data(selenium):
    import base64
    canvas_tag_property = "//canvas[starts-with(@id, 'matplotlib')]"
    canvas_element = selenium.driver.find_element_by_xpath(canvas_tag_property)
    img_script = "return arguments[0].toDataURL('image/png').substring(21)"
    canvas_base64 = selenium.driver.execute_script(img_script, canvas_element)
    canvas_png = base64.b64decode(canvas_base64)
    with open(TEST_PATH /
              r"canvas-{0}.png".format(selenium.browser), 'wb') as f:
        f.write(canvas_png)


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

    # If we don't have a reference image, write one to disk
    if not os.path.isfile('test/canvas-{0}.png'.format(selenium.browser)):
        get_canvas_data(selenium)

    selenium.run("""
    url = 'test/canvas-{0}.png'
    threshold = 0
    plt.gcf().canvas.compare_reference_image(url, threshold)
    """.format(selenium.browser))

    wait = WebDriverWait(selenium.driver, timeout=70)
    wait.until(ResultLoaded())
    assert selenium.run("window.deviation") == 0
    assert selenium.run("window.result") is True


class ResultLoaded:
    def __call__(self, driver):
        inited = driver.execute_script("return window.result")
        return inited is not None
