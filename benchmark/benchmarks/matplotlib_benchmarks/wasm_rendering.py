# non-native
# setup: import matplotlib ; import numpy as np ; matplotlib.use('module://matplotlib.backends.wasm_backend') ; from matplotlib import pyplot as plt
# run: wasm_rendering()

# pythran export wasm_rendering()
import matplotlib
import numpy as np

matplotlib.use("module://matplotlib.backends.wasm_backend")
from matplotlib import pyplot as plt  # noqa: E402


def wasm_rendering():
    t = np.arange(0.0, 2.0, 0.01)
    s = 1 + np.sin(2 * np.pi * t)
    plt.figure()
    plt.plot(t, s, linewidth=1.0, marker=11)
    plt.plot(t, t)
    plt.grid(True)
    plt.show()
    plt.close("all")
    plt.clf()
