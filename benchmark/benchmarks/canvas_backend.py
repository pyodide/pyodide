# non-native
# setup: import matplotlib.pyplot as plt  # noqa
# run: canvas_backend()

# pythran export canvas_backend()
import matplotlib.pyplot as plt


def canvas_backend():
    plt.plot([1, 2, 3])
    plt.show()
