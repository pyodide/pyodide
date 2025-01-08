# non-native
# setup: import matplotlib ; import numpy as np ;  matplotlib.use('module://matplotlib_pyodide.wasm_backend') ; from matplotlib import pyplot as plt ; import matplotlib.cm as cm
# run: wasm_image()

# pythran export wasm_image()
import matplotlib
import numpy as np

matplotlib.use("module://matplotlib_pyodide.wasm_backend")

from matplotlib import cm  # noqa: E402
from matplotlib import pyplot as plt  # noqa: E402


def wasm_image():
    delta = 0.025
    x = y = np.arange(-3.0, 3.0, delta)
    X, Y = np.meshgrid(x, y)
    Z1 = np.exp(-(X**2) - Y**2)
    Z2 = np.exp(-((X - 1) ** 2) - (Y - 1) ** 2)
    Z = (Z1 - Z2) * 2
    plt.figure()
    plt.imshow(
        Z,
        interpolation="bilinear",
        cmap=cm.RdYlGn,
        origin="lower",
        extent=[-3, 3, -3, 3],
        vmax=abs(Z).max(),
        vmin=-abs(Z).max(),
    )
    plt.show()
    plt.close("all")
    plt.clf()
