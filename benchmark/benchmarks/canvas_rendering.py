# non-native
# setup: from matplotlib import pyplot as plt ; import numpy as np  # noqa
# run: canvas_rendering()

# pythran export canvas_rendering()
from matplotlib import pyplot as plt
import numpy as np


def canvas_rendering():
    t = np.arange(0.0, 2.0, 0.01)
    s = 1 + np.sin(2 * np.pi * t)
    plt.figure()
    plt.plot(t, s, linewidth=1.0, marker=11)
    plt.plot(t, t)
    plt.grid(True)
    plt.show()
