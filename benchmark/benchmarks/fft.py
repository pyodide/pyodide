#setup: N = 2**11 ; import numpy ; a = numpy.array(numpy.random.rand(N), dtype=complex)
#run: fft(a)

#pythran export fft(complex [])

import numpy as np

fft = np.fft
