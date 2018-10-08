# setup: N = 5000 ; import numpy as np ; t0, p0, t1, p1 = np.random.randn(N), np.random.randn(N), np.random.randn(N), np.random.randn(N)  # noqa
# run: arc_distance(t0, p0, t1, p1)

# pythran export arc_distance(float64 [], float64[], float64[], float64[])

import numpy as np


def arc_distance(theta_1, phi_1, theta_2, phi_2):
    """
    Calculates the pairwise arc distance between all points in vector a and b.
    """
    temp = (np.sin((theta_2 - theta_1) / 2)**2 + np.cos(theta_1)
            * np.cos(theta_2) * np.sin((phi_2 - phi_1) / 2)**2)
    distance_matrix = 2 * (np.arctan2(np.sqrt(temp), np.sqrt(1 - temp)))
    return distance_matrix
