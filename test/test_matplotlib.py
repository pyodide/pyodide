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
    from js import Request, window
    from matplotlib import pyplot as plt
    import numpy as np
    import pyodide, io
    t = np.arange(0.0, 2.0, 0.01)
    s = 1 + np.sin(2 * np.pi * t)
    plt.plot(t, s, linewidth=1.0, marker=11)
    plt.plot(t, t)
    plt.grid(True)
    plt.show()
    canvas_data = plt.gcf().canvas.get_pixel_data()
    """)
    selenium.run("""
    def func(response):
        return response.blob()
    """)
    selenium.run("""
    req = Request.new('test/canvas.png')
    resp = window.fetch(req).then(func)
    ref_data = io.BytesIO(resp)
    """)
