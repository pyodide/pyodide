# setup: N = 2**11 ; import numpy ; a = numpy.array(numpy.random.rand(N), dtype=complex)  # noqa
# run: fft(a)

# pythran export fft(complex [])

import numpy as np


def fft(x):
    return np.fft(x)
