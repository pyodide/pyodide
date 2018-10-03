# http://stackoverflow.com/questions/16541618/perform-a-reverse-cumulative-sum-on-a-numpy-array
# pythran export reverse_cumsum(float[])
# setup: import numpy as np ; r = np.random.rand(1000000)
# run: reverse_cumsum(r)
import numpy as np


def reverse_cumsum(x):
    return np.cumsum(x[::-1])[::-1]
