# http://stackoverflow.com/questions/4651683/numpy-grouping-using-itertools-groupby-performance
# setup: import numpy as np ; N = 350000 ; values = np.array(np.random.randint(0,3298,size=N),dtype='u4') ; values.sort()  # noqa
# run: grouping(values)

# pythran export grouping(uint32 [])


def grouping(values):
    import numpy as np
    diff = np.concatenate(([1], np.diff(values)))
    idx = np.concatenate((np.where(diff)[0], [len(values)]))
    return values[idx[:-1]], np.diff(idx)
