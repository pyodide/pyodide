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
    from js import XMLHttpRequest, window
    window.testing = True
    from matplotlib import pyplot as plt
    from matplotlib import _png
    import numpy as np
    import io
    t = np.arange(0.0, 2.0, 0.01)
    s = 1 + np.sin(2 * np.pi * t)
    plt.plot(t, s, linewidth=1.0, marker=11)
    plt.plot(t, t)
    plt.grid(True)
    plt.show()
    canvas_data = plt.gcf().canvas.get_pixel_data()
    """)
    selenium.run("""
    def _get_url_async(url, cb):
        req = XMLHttpRequest.new()
        req.open('GET', url, True)
        req.responseType = 'arraybuffer'

        def callback(e):
            if req.readyState == 4:
                ref_data = cb(io.BytesIO(req.response))
                window.result = np.mean(np.abs(canvas_data - ref_data))

        req.onreadystatechange = callback
        req.send(None)
    """)
    selenium.run("_get_url_async('test/plot.png', _png.read_png_int)")
    wait = WebDriverWait(selenium.driver, timeout=70)
    wait.until(ResultLoaded())
    res = selenium.run("window.result")
    selenium.get_canvas_data()
    assert res is True


class ResultLoaded:
    def __call__(self, driver):
        inited = driver.execute_script("return window.result")
        return inited is not None
