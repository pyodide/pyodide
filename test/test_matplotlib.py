import os
from selenium.webdriver.support.wait import WebDriverWait


def test_matplotlib(selenium_standalone):
    selenium = selenium_standalone
    selenium.load_package("matplotlib")
    selenium.run("from matplotlib import pyplot as plt")
    selenium.run("plt.figure()")
    selenium.run("plt.plot([1,2,3])")
    selenium.run("plt.show()")


def test_svg(selenium):
    selenium.load_package("matplotlib")
    selenium.run("from matplotlib import pyplot as plt")
    selenium.run("plt.figure()")
    selenium.run("x = plt.plot([1,2,3])")
    selenium.run("import io")
    selenium.run("fd = io.BytesIO()")
    selenium.run("plt.savefig(fd, format='svg')")
    content = selenium.run("fd.getvalue().decode('utf8')")
    assert len(content) == 15752
    assert content.startswith("<?xml")


def test_pdf(selenium):
    selenium.load_package("matplotlib")
    selenium.run("from matplotlib import pyplot as plt")
    selenium.run("plt.figure()")
    selenium.run("x = plt.plot([1,2,3])")
    selenium.run("import io")
    selenium.run("fd = io.BytesIO()")
    selenium.run("plt.savefig(fd, format='pdf')")


def test_rendering(selenium):
    selenium.load_package("matplotlib")
    selenium.run("""
    from js import window
    window.testing = True
    from matplotlib import pyplot as plt
    import numpy as np
    t = np.arange(0.0, 2.0, 0.01)
    s = 1 + np.sin(2 * np.pi * t)
    plt.plot(t, s, linewidth=1.0, marker=11)
    plt.plot(t, t)
    plt.grid(True)
    plt.show()
    """)

    if not os.path.isfile('test/canvas-{0}.png'.format(selenium.browser)):
        selenium.get_canvas_data()

    selenium.run("""
    url = 'test/canvas-{0}.png'
    threshold = 0
    plt.gcf().canvas.compare_reference_image(url, threshold)
    """.format(selenium.browser))

    wait = WebDriverWait(selenium.driver, timeout=70)
    wait.until(ResultLoaded())
    assert selenium.run("window.result") is True


class ResultLoaded:
    def __call__(self, driver):
        inited = driver.execute_script("return window.result")
        return inited is not None
