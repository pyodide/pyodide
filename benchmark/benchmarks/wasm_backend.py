# non-native
# setup: import matplotlib ; matplotlib.use('module://matplotlib.backends.wasm_backend') ; import matplotlib.pyplot as plt  # noqa
# run: wasm_backend()

# pythran export wasm_backend()
import matplotlib
matplotlib.use('module://matplotlib.backends.wasm_backend')
import matplotlib.pyplot as plt  # noqa: E402


def wasm_backend():
    plt.plot([1, 2, 3])
    plt.show()
