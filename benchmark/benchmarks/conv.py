#setup: N = 10 ; import numpy as np ; x = np.tri(N,N)*0.5 ; w = np.tri(5,5)*0.25
#run: conv(x,w)

#pythran export conv(float[][], float[][])
import numpy as np

def clamp(i, offset, maxval):
    j = max(0, i + offset)
    return min(j, maxval)


def reflect(pos, offset, bound):
    idx = pos+offset
    return min(2*(bound-1)-idx,max(idx,-idx))


def conv(x, weights):
    sx = x.shape
    sw = weights.shape
    result = np.zeros_like(x)
    for i in range(sx[0]):
        for j in range(sx[1]):
            for ii in range(sw[0]):
                for jj in range(sw[1]):
                    idx = clamp(i,ii-sw[0]//2,sw[0]), clamp(j,jj-sw[0]//2,sw[0])
                    result[i,j] += x[idx] * weights[ii,jj]
    return result
