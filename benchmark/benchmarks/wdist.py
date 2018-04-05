#from: http://stackoverflow.com/questions/19277244/fast-weighted-euclidean-distance-between-points-in-arrays/19277334#19277334
#setup: import numpy as np ; N = 10 ; A = np.random.rand(N,N) ; B =  np.random.rand(N,N) ; W = np.random.rand(N,N)
#run: wdist(A,B,W)

#pythran export wdist(float64 [][], float64 [][], float64[][])

import numpy as np
def wdist(A, B, W):

    k,m = A.shape
    _,n = B.shape
    D = np.zeros((m, n))

    for ii in range(m):
        for jj in range(n):
            wdiff = (A[:,ii] - B[:,jj]) / W[:,ii]
            D[ii,jj] = np.sqrt((wdiff**2).sum())
    return D
