# from: http://stackoverflow.com/questions/17112550/python-and-numba-for-vectorized-functions # noqa
# setup: import numpy as np ; N = 100000 ; a, b, c = np.random.rand(N), np.random.rand(N), np.random.rand(N)  # noqa
# run: vibr_energy(a, b, c)

# pythran export vibr_energy(float64[], float64[], float64[])
import numpy


def vibr_energy(harmonic, anharmonic, i):
    return numpy.exp(-harmonic * i - anharmonic * (i ** 2))
