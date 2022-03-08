# non-native
# setup: import matplotlib ; import numpy as np ; matplotlib.use('module://matplotlib.backends.html5_canvas_backend') ; from matplotlib import pyplot as plt ;
# run: canvas_custom_font()

# pythran export canvas_custom_font()
import matplotlib
import numpy as np

matplotlib.use("module://matplotlib.backends.html5_canvas_backend")
from matplotlib import pyplot as plt  # noqa: E402


def canvas_custom_font():
    f = {"fontname": "cmsy10"}
    t = np.arange(0.0, 2.0, 0.01)
    s = 1 + np.sin(2 * np.pi * t)
    plt.figure()
    plt.title("A simple Sine Curve", **f)
    plt.plot(t, s, linewidth=1.0, marker=11)
    plt.plot(t, t)
    plt.grid(True)
    plt.show()
    plt.close("all")
    plt.clf()
