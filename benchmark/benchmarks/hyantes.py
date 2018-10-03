# setup: import numpy ; a = numpy.array([ [i/10., i/10., i/20.] for i in range(44440)], dtype=numpy.double)  # noqa
# run: hyantes(0, 0, 90, 90, 1, 100, 80, 80, a)

# pythran export hyantes(float, float, float, float, float, float, int,
# int, float[][])
import numpy as np


def hyantes(xmin, ymin, xmax, ymax, step, range_, range_x, range_y, t):
    X, Y = t.shape
    pt = np.zeros((X, Y))
    for i in range(X):
        for j in range(Y):
            for k in t:
                tmp = (6368. * np.arccos(np.cos(xmin + step * i)
                       * np.cos(k[0]) * np.cos((ymin + step * j) - k[1])
                       + np.sin(xmin + step * i) * np.sin(k[0])))
                if tmp < range_:
                    pt[i, j] += k[2] / (1 + tmp)
    return pt
