# non-native
# setup: import matplotlib.pyplot as plt ; import numpy as np ;  # noqa
# run: canvas_custom_font()

# pythran export canvas_custom_font()
import matplotlib.pyplot as plt
import numpy as np


def canvas_custom_font():
    f = {'fontname': 'cmsy10'}
    t = np.arange(0.0, 2.0, 0.01)
    s = 1 + np.sin(2 * np.pi * t)
    plt.figure()
    plt.title('A simple Sine Curve', **f)
    plt.plot(t, s, linewidth=1.0, marker=11)
    plt.plot(t, t)
    plt.grid(True)
    plt.show()
