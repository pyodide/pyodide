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
    selenium.run("from matplotlib import pyplot as plt")
    selenium.run("import numpy as np")
    selenium.run("import pyodide, io")
    selenium.run("t = np.arange(0.0, 2.0, 0.01)")
    selenium.run("s = 1 + np.sin(2 * np.pi * t)")
    selenium.run("plt.plot(t, s, linewidth=1.0, marker=11)")
    selenium.run("plt.plot(t, t)")
    selenium.run("plt.grid(True)")
    selenium.run("plt.show()")
    selenium.run("canvas_data = plt.gcf().canvas.get_pixel_data()")
    selenium.run("ref_data = pyodide.open_url('test/canvas.png').getvalue()")
    ref_data = selenium.run("io.open(ref_data, encoding='rb', buffering = 0)")
    assert ref_data == 1
