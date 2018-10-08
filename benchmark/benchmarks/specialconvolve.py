# from: http://stackoverflow.com/questions/2196693/improving-numpy-performance
# pythran export specialconvolve(uint32 [][])
# setup: import numpy as np ; r = np.arange(100*10000, dtype=np.uint32).reshape(1000,1000)  # noqa
# run: specialconvolve(r)


def specialconvolve(a):
    # sorry, you must pad the input yourself
    rowconvol = a[1:-1, :] + a[:-2, :] + a[2:, :]
    colconvol = rowconvol[:, 1:-1] + rowconvol[:, :-2] + \
        rowconvol[:, 2:] - 9 * a[1:-1, 1:-1]
    return colconvol
