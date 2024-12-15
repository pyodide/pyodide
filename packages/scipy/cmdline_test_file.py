import numpy as np
from scipy.sparse.linalg import svds

rng = np.random.default_rng(0)
A = rng.random((10, 10))

res = svds(A, k=3, which="LM", random_state=0)
print("res", res)
