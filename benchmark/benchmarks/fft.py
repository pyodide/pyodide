#setup: N = 2**10 ; import numpy ; a = numpy.array(numpy.random.rand(N), dtype=complex)
#run: fft(a)

#pythran export fft(complex [])

import math, numpy as np

def fft(x):
   N = x.shape[0]
   if N == 1:
       return np.array(x)
   e=fft(x[::2])
   o=fft(x[1::2])
   M=N//2
   l=[ e[k] + o[k]*math.e**(-2j*math.pi*k/N) for k in range(M) ]
   r=[ e[k] - o[k]*math.e**(-2j*math.pi*k/N) for k in range(M) ]
   return np.array(l+r)

